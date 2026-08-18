"""
Module: test_regression_gate
Layer: test (unit)
Purpose: RED anchor + behaviour tests for evals/regression_gate.py — the
         EVAL-P23.2 threshold logic. A rate regresses only when its CI UPPER
         bound falls below the baseline's point estimate; a point-estimate
         comparison at k=3 fires on sampling noise, so overlapping intervals
         must never trigger. (This docstring said "lower bound" until
         2026-08-18 — the same inverted statement Defect C found in
         check_regression's own docstring. The code was always correct;
         the prose was the trap, and this file is where someone reads the
         rule before touching the gate.)
Dependencies: pytest; trend_store, paired_stats, regression_gate (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from paired_stats import PairedResult
from regression_gate import check_regression, format_regression_report
from trend_store import RateWithCI, TrendRow


def _row(gen_id: str, *, guard: RateWithCI | None = None, capability: RateWithCI | None = None,
         inconclusive_rate: float | None = 0.0) -> TrendRow:
    return TrendRow(
        gen_id=gen_id,
        harness_version="v1",
        recorded_at="2026-08-17T00:00:00+00:00",
        guard=guard,
        capability=capability,
        inconclusive_rate=inconclusive_rate,
    )


def _paired(verdict: str, regressed: int = 5, improved: int = 1) -> PairedResult:
    return PairedResult(
        improved=improved, regressed=regressed, unchanged=10, p_value=0.01, verdict=verdict,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_overlapping_intervals_do_not_trigger_a_regression() -> None:
    """Candidate's point estimate is lower than the baseline's, but its CI
    still reaches back up past the baseline's point estimate — a
    point-estimate comparison would fire here, but the CI-must-move-
    entirely-below rule must not, because that is exactly the
    sampling-noise case at k=3. (Regression test for a real bug: comparing
    candidate.ci_LOW against baseline.rate instead of candidate.ci_HIGH
    fires here incorrectly, because a CI's lower bound is always below its
    own point estimate — confirmed by re-running this exact comparison
    with identical before/after data and observing a false positive before
    the fix.)"""
    baseline = _row("gen_base", guard=RateWithCI(rate=0.90, ci_low=0.85, ci_high=0.95, n=94))
    candidate = _row("gen_new", guard=RateWithCI(rate=0.87, ci_low=0.80, ci_high=0.93, n=94))
    # candidate.rate (0.87) < baseline.rate (0.90), but candidate's CI upper
    # bound (0.93) still reaches above baseline's point estimate — no fire.
    report = check_regression(candidate, baseline)
    assert report.regressed is False
    assert report.findings == ()


def test_real_drop_below_baseline_point_estimate_fires() -> None:
    """A genuine drop — candidate's entire CI below the baseline's point
    estimate — must fire, and the message must name the metric, both
    intervals, and n."""
    baseline = _row("gen_base", guard=RateWithCI(rate=0.90, ci_low=0.85, ci_high=0.95, n=94))
    candidate = _row("gen_new", guard=RateWithCI(rate=0.70, ci_low=0.60, ci_high=0.78, n=94))
    report = check_regression(candidate, baseline)
    assert report.regressed is True
    assert len(report.findings) == 1
    f = report.findings[0]
    assert f.metric == "guard"
    assert "0.70" in f.message  # candidate rate
    assert "0.90" in f.message  # baseline point estimate
    assert "94" in f.message    # n


# ---------------------------------------------------------------------------
# Behaviour: the other two regression classes
# ---------------------------------------------------------------------------


def test_mcnemar_worse_verdict_fires_regardless_of_rates() -> None:
    baseline = _row("gen_base", guard=RateWithCI(rate=0.90, ci_low=0.85, ci_high=0.95, n=94))
    candidate = _row("gen_new", guard=RateWithCI(rate=0.95, ci_low=0.90, ci_high=0.98, n=94))
    report = check_regression(candidate, baseline, paired=_paired("worse"))
    assert report.regressed is True
    assert any(f.metric == "paired_mcnemar" for f in report.findings)


def test_mcnemar_better_or_no_change_does_not_fire() -> None:
    baseline = _row("gen_base", guard=RateWithCI(rate=0.90, ci_low=0.85, ci_high=0.95, n=94))
    candidate = _row("gen_new", guard=RateWithCI(rate=0.92, ci_low=0.91, ci_high=0.96, n=94))
    for verdict in ("better", "no_detectable_change"):
        report = check_regression(candidate, baseline, paired=_paired(verdict))
        assert report.regressed is False


def test_inconclusive_rate_above_threshold_fires() -> None:
    baseline = _row("gen_base")
    candidate = _row("gen_new", inconclusive_rate=0.35)
    report = check_regression(candidate, baseline, max_inconclusive_rate=0.20)
    assert report.regressed is True
    assert any(f.metric == "inconclusive_rate" for f in report.findings)


def test_inconclusive_rate_at_threshold_does_not_fire() -> None:
    baseline = _row("gen_base")
    candidate = _row("gen_new", inconclusive_rate=0.20)
    report = check_regression(candidate, baseline, max_inconclusive_rate=0.20)
    assert report.regressed is False


def test_missing_rate_on_either_side_is_not_a_regression_call() -> None:
    """An unmeasured rate is a validity problem, not this function's job to flag."""
    baseline = _row("gen_base", guard=None)
    candidate = _row("gen_new", guard=RateWithCI(rate=0.5, ci_low=0.4, ci_high=0.6, n=10))
    report = check_regression(candidate, baseline)
    assert report.regressed is False


def test_multiple_findings_all_reported_together() -> None:
    baseline = _row(
        "gen_base",
        guard=RateWithCI(rate=0.90, ci_low=0.85, ci_high=0.95, n=94),
        capability=RateWithCI(rate=0.80, ci_low=0.72, ci_high=0.87, n=48),
    )
    candidate = _row(
        "gen_new",
        guard=RateWithCI(rate=0.70, ci_low=0.60, ci_high=0.78, n=94),
        capability=RateWithCI(rate=0.60, ci_low=0.50, ci_high=0.68, n=48),
        inconclusive_rate=0.5,
    )
    report = check_regression(candidate, baseline, paired=_paired("worse"))
    assert len(report.findings) == 4
    assert {f.metric for f in report.findings} == {
        "guard", "capability", "paired_mcnemar", "inconclusive_rate",
    }


# ---------------------------------------------------------------------------
# format_regression_report
# ---------------------------------------------------------------------------


def test_format_no_regression() -> None:
    baseline = _row("gen_base", guard=RateWithCI(rate=0.90, ci_low=0.85, ci_high=0.95, n=94))
    candidate = _row("gen_new", guard=RateWithCI(rate=0.92, ci_low=0.91, ci_high=0.96, n=94))
    report = check_regression(candidate, baseline)
    assert format_regression_report(report) == "NO REGRESSION DETECTED"


def test_format_lists_every_finding() -> None:
    baseline = _row("gen_base", guard=RateWithCI(rate=0.90, ci_low=0.85, ci_high=0.95, n=94))
    candidate = _row("gen_new", guard=RateWithCI(rate=0.70, ci_low=0.60, ci_high=0.78, n=94))
    report = check_regression(candidate, baseline)
    text = format_regression_report(report)
    assert "REGRESSION DETECTED" in text
    assert "[guard]" in text


# ---------------------------------------------------------------------------
# The stated rule must match the implemented one — EVAL-P23 Defect C
# ---------------------------------------------------------------------------


def test_check_regression_docstring_states_the_implemented_rule() -> None:
    """regression_gate.py exists partly to document the WRONG version of this
    rule so it cannot be quietly reintroduced (DEC-185: the ci_low comparison
    fires on a run compared against itself). A docstring asserting that wrong
    version is therefore an active trap, not a typo: the next person to "fix"
    the code to match the prose reintroduces the bug the module was written to
    prevent. check_regression's own docstring must state the upper-bound rule
    the code implements."""
    doc = (check_regression.__doc__ or "").lower()
    assert "upper bound" in doc
    assert "lower bound" not in doc  # the inverted rule must not be restated as the policy
