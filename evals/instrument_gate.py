"""
Module: instrument_gate
Layer: evals (eval harness — not part of src/)
Purpose: Decide whether the *measuring instrument* degraded between two runs —
         inter-judge agreement falling — as a verdict distinct from the engine
         regressing (EVAL-P23 Defect E). Separating "my engine got worse" from
         "my ruler got worse" is the point: conflating them sends the maintainer
         debugging the wrong system.
Dependencies: pydantic; panel_metric_records (PanelKappa), trend_store (TrendRow)
Used by: scripts/record_trend_and_gate.py (exit code 3)
Does NOT: read files, compute kappa (kappa_stats/panel_metrics own the
         arithmetic), or judge the engine's rates (regression_gate does).

WHY THIS IS A THIRD VERDICT AND NOT A FOURTH REGRESSION FINDING
A regression finding says "the engine's measured quality dropped, act on the
engine". A kappa drop says the opposite: the numbers this run produced are less
trustworthy than the baseline's, so the rate comparison sitting beside it cannot
be read as an engine result at all. Returning that as `regressed=True` would
label a judge problem an engine problem. With refusal_judge at kappa 0.225 and
affirms_judge at 0.282 (DEC-188, ISSUE-184) this is not hypothetical.

WHY THE SAME ONE-SIDED CI RULE AS THE RATE CHECK
kappa's clustered bootstrap CI on the real corpus is [0.227, 0.730] — wider than
most drops worth acting on. A point-estimate comparison would fire almost every
run; requiring the candidate's entire interval to sit below the baseline's point
estimate means overlapping intervals never fire, exactly as in
regression_gate._rate_regressed. See DEC-185 for what the inverted version does.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from panel_metric_records import PanelKappa
from trend_store import TrendRow

_KAPPA_METRIC: str = "panel_kappa"


class InstrumentFinding(BaseModel):
    """One reason the measuring instrument was judged to have degraded.

    Attributes:
        metric: Which agreement metric fired ('panel_kappa').
        message: Human-readable explanation naming both kappas, both intervals
            and n — never a bare "agreement fell".
    """

    model_config = ConfigDict(frozen=True)

    metric: str
    message: str


class InstrumentReport(BaseModel):
    """Outcome of checking a candidate run's judge agreement against a baseline.

    Attributes:
        degraded: True when agreement fell far enough that this run's rate
            comparison is not trustworthy.
        checked: False when the check could not run at all (no panel kappa, or
            no interval to compare with). Reported separately from `degraded`
            so a skipped check is never read as a passed one.
        findings: Every reason the gate fired; empty when degraded is False.
        skip_reason: Why the check did not run; empty when checked is True.
    """

    model_config = ConfigDict(frozen=True)

    degraded: bool
    checked: bool
    findings: tuple[InstrumentFinding, ...] = ()
    skip_reason: str = ""


def _unusable(kappa: PanelKappa | None) -> bool:
    """True when this side carries no kappa the one-sided CI rule can use."""
    return kappa is None or kappa.kappa is None


def _skip(reason: str) -> InstrumentReport:
    """Build the report for a check that could not run."""
    return InstrumentReport(degraded=False, checked=False, skip_reason=reason)


def _finding(candidate: PanelKappa, baseline: PanelKappa) -> InstrumentFinding:
    """Build the named finding for a kappa that moved entirely below baseline."""
    return InstrumentFinding(
        metric=_KAPPA_METRIC,
        message=(
            f"inter-judge kappa {candidate.kappa:.3f} "
            f"[{candidate.ci_low:.3f}, {candidate.ci_high:.3f}] (n={candidate.n_items}) "
            f"sits entirely below baseline point estimate {baseline.kappa:.3f} "
            f"(n={baseline.n_items}) — the judges agree less than they did, so this "
            "run's rate comparison is not trustworthy and the engine is not "
            "necessarily at fault"
        ),
    )


def check_instrument(candidate: TrendRow, baseline: TrendRow) -> InstrumentReport:
    """Check whether judge agreement degraded between baseline and candidate.

    Args:
        candidate: The new run's trend row.
        baseline: The comparability-checked prior run (baseline_selection).
    Returns:
        An InstrumentReport. `checked=False` whenever either side lacks a panel
        kappa (a single-judge run has none) or the candidate lacks the bootstrap
        interval the one-sided rule needs — an unmeasurable instrument is
        reported as unmeasured, never as stable.
    """
    cand, base = candidate.panel_kappa, baseline.panel_kappa
    if _unusable(cand) or _unusable(base):
        return _skip(
            "no panel kappa on both sides — a single-judge run records none, so "
            "there is no agreement to compare"
        )
    assert cand is not None and base is not None and base.kappa is not None  # narrowed by _unusable
    if cand.ci_high is None or cand.ci_low is None:
        return _skip(
            "the candidate's kappa carries no bootstrap interval; gating on point "
            "estimates alone fires on noise (DEC-185), so no check is made"
        )
    if cand.ci_high < base.kappa:
        return InstrumentReport(degraded=True, checked=True, findings=(_finding(cand, base),))
    return InstrumentReport(degraded=False, checked=True)


def format_instrument_report(report: InstrumentReport) -> str:
    """Render an InstrumentReport as console lines.

    Args:
        report: The InstrumentReport to render.
    Returns:
        Multi-line string, opening with one of "INSTRUMENT DEGRADED:",
        "INSTRUMENT STABLE" or "INSTRUMENT CHECK SKIPPED:" — three states, so a
        run whose agreement was never measured cannot read as one whose
        agreement held.
    """
    if not report.checked:
        return f"INSTRUMENT CHECK SKIPPED: {report.skip_reason}"
    if not report.degraded:
        return "INSTRUMENT STABLE (inter-judge agreement did not fall)"
    lines = ["INSTRUMENT DEGRADED:"]
    lines.extend(f"  [{f.metric}] {f.message}" for f in report.findings)
    return "\n".join(lines)
