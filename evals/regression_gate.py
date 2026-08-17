"""
Module: regression_gate
Layer: evals (eval harness — not part of src/)
Purpose: Encode what counts as a regression between a candidate run and its
         trend-store baseline (EVAL-P23.2), so a drop is caught by exit code
         rather than by someone eyeballing two numbers. A rate regresses when
         its entire CI (candidate.ci_high) falls below the baseline's point
         estimate — using the interval, not the point estimate, because a
         point-estimate comparison at k=3 fires on sampling noise (the same
         reasoning paired_stats.py already applies to McNemar). Comparing
         against candidate.ci_low instead is a tempting-looking bug: a CI's
         lower bound is *always* below its own point estimate, so that
         comparison fires on nearly every pair of runs, even a run against
         itself — caught empirically comparing k3_73e6c36 to itself before
         this module shipped. A McNemar 'worse' verdict or an inconclusive
         rate above threshold also regress.
Dependencies: pydantic; trend_store (RateWithCI, TrendRow), paired_stats (PairedResult)
Used by: tests/unit/evals/test_regression_gate.py; scripts/Run-EvalHarness.ps1
         (EVAL-P23.3)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from paired_stats import PairedResult
from trend_store import RateWithCI, TrendRow

# Matches summary._MAX_INCONCLUSIVE_RATE — duplicated rather than imported so
# this module has no dependency on summary.py's internals; both values encode
# the same policy decision (a run where >20% of judged expectations returned
# no verdict provides false confidence) and must be changed together if ever
# revisited. See docs/REGRESSION_POLICY.md.
DEFAULT_MAX_INCONCLUSIVE_RATE: float = 0.20


class RegressionFinding(BaseModel):
    """One reason a candidate run was flagged as a regression.

    Attributes:
        metric: Which metric fired ('guard', 'capability', 'paired_mcnemar',
            'inconclusive_rate').
        message: Human-readable explanation naming the metric, both
            intervals (or values), and n — never a bare "regressed".
    """

    model_config = ConfigDict(frozen=True)

    metric: str
    message: str


class RegressionReport(BaseModel):
    """Outcome of checking a candidate run against its baseline.

    Attributes:
        regressed: True if any finding fired.
        findings: Every reason the gate fired; empty when regressed is False.
    """

    model_config = ConfigDict(frozen=True)

    regressed: bool
    findings: tuple[RegressionFinding, ...]


def _rate_regressed(candidate: RateWithCI | None, baseline: RateWithCI | None) -> bool:
    """True when candidate's entire CI sits below baseline's point estimate.

    A Wilson CI's lower bound is *always* below its own point estimate — that
    is simply what a confidence interval is. Comparing candidate.ci_low
    against baseline.rate therefore fires on nearly every pair of runs,
    including a run compared against itself (confirmed empirically:
    identical k3_73e6c36 numbers on both sides still fired under that
    comparison). The correct one-sided test is candidate.ci_HIGH — even in
    the best case for the candidate, is it still below where the baseline
    sat? That is what "the interval moved entirely below the baseline"
    means, and it is the only reading under which overlapping intervals
    never fire.

    Args:
        candidate: The new run's rate; None means it wasn't measured.
        baseline: The baseline's rate; None means nothing to compare against.
    Returns:
        False whenever either side is unmeasurable — an unmeasured rate is a
        different failure (a validity problem) than a measured regression,
        and this function's only job is the regression call.
    """
    if candidate is None or baseline is None:
        return False
    candidate_ci_high: float | None = candidate.ci_high
    baseline_rate: float | None = baseline.rate
    if candidate.rate is None or baseline_rate is None or candidate_ci_high is None:
        return False
    # bool(...): pydantic field access on RateWithCI resolves as Any to mypy here
    # (no-any-return otherwise) even with the explicit float | None annotations
    # above — this is a type-checker gap, not a real runtime ambiguity; the
    # comparison already yields a genuine bool.
    return bool(candidate_ci_high < baseline_rate)


def _rate_finding(metric: str, candidate: RateWithCI, baseline: RateWithCI) -> RegressionFinding:
    """Build the named finding for a regressed rate — names both intervals and n."""
    return RegressionFinding(
        metric=metric,
        message=(
            f"{metric} rate {candidate.rate:.3f} "
            f"[{candidate.ci_low:.3f}, {candidate.ci_high:.3f}] (n={candidate.n}) "
            f"sits entirely below baseline point estimate {baseline.rate:.3f} "
            f"[{baseline.ci_low:.3f}, {baseline.ci_high:.3f}] (n={baseline.n})"
        ),
    )


def _paired_finding(paired: PairedResult) -> RegressionFinding:
    """Build the named finding for a McNemar 'worse' verdict."""
    return RegressionFinding(
        metric="paired_mcnemar",
        message=(
            f"paired McNemar verdict=worse: {paired.regressed} regressed vs "
            f"{paired.improved} improved (p={paired.p_value:.4f})"
        ),
    )


def _inconclusive_finding(rate: float, threshold: float) -> RegressionFinding:
    """Build the named finding for an over-threshold inconclusive rate."""
    return RegressionFinding(
        metric="inconclusive_rate",
        message=f"inconclusive rate {rate:.3f} exceeds threshold {threshold:.3f}",
    )


def check_regression(
    candidate: TrendRow,
    baseline: TrendRow,
    *,
    paired: PairedResult | None = None,
    max_inconclusive_rate: float = DEFAULT_MAX_INCONCLUSIVE_RATE,
) -> RegressionReport:
    """Check a candidate run against its baseline for every regression class.

    Args:
        candidate: The new run's trend row.
        baseline: The comparability-checked prior run to compare against
            (typically trend_store.latest_row()).
        paired: Case-level McNemar comparison, when available (compare.py);
            None skips this check rather than treating it as a pass.
        max_inconclusive_rate: Threshold above which the inconclusive rate
            itself is a regression, regardless of the published rates.
    Returns:
        RegressionReport naming every finding that fired. Overlapping CIs
        never fire — only a CI lower bound strictly below the baseline's
        point estimate counts.
    """
    findings: list[RegressionFinding] = []

    if _rate_regressed(candidate.guard, baseline.guard):
        # _rate_regressed already returned True, which is only possible when
        # both sides are non-None (see its own None-guards) — asserting here
        # narrows the type for the call below instead of silencing mypy.
        assert candidate.guard is not None and baseline.guard is not None
        findings.append(_rate_finding("guard", candidate.guard, baseline.guard))
    if _rate_regressed(candidate.capability, baseline.capability):
        assert candidate.capability is not None and baseline.capability is not None
        findings.append(_rate_finding("capability", candidate.capability, baseline.capability))
    if paired is not None and paired.verdict == "worse":
        findings.append(_paired_finding(paired))
    if candidate.inconclusive_rate is not None and candidate.inconclusive_rate > max_inconclusive_rate:
        findings.append(_inconclusive_finding(candidate.inconclusive_rate, max_inconclusive_rate))

    return RegressionReport(regressed=bool(findings), findings=tuple(findings))


def format_regression_report(report: RegressionReport) -> str:
    """Render a RegressionReport as console lines.

    Args:
        report: The RegressionReport to render.
    Returns:
        Multi-line string; "NO REGRESSION DETECTED" when findings is empty.
    """
    if not report.regressed:
        return "NO REGRESSION DETECTED"
    lines = ["REGRESSION DETECTED:"]
    lines.extend(f"  [{f.metric}] {f.message}" for f in report.findings)
    return "\n".join(lines)
