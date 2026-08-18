"""
Module: test_instrument_gate
Layer: test (unit)
Purpose: RED anchor + behaviour tests for evals/instrument_gate.py — the third
         verdict (EVAL-P23 Defect E). A fall in inter-judge agreement means the
         ruler moved, not necessarily the engine; conflating that with a rate
         regression sends the maintainer debugging the wrong system. With
         refusal_judge at kappa 0.225 (DEC-188 / ISSUE-184) this fires in practice.
Dependencies: pytest; instrument_gate, panel_metric_records, trend_store (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from instrument_gate import check_instrument, format_instrument_report
from panel_metric_records import PanelKappa
from trend_store import RateWithCI, TrendRow


def _row(gen_id: str, *, kappa: PanelKappa | None = None, guard: RateWithCI | None = None) -> TrendRow:
    return TrendRow(
        gen_id=gen_id,
        harness_version="v1",
        recorded_at="2026-08-17T00:00:00+00:00",
        guard=guard,
        panel_kappa=kappa,
    )


# ---------------------------------------------------------------------------
# RED anchors
# ---------------------------------------------------------------------------


def test_kappa_drop_is_a_distinct_verdict_from_a_rate_regression() -> None:
    """The rates are identical on both sides — nothing about the engine's
    measured performance moved. Only agreement fell, so this must surface as
    its own verdict rather than as (or alongside) an engine regression."""
    rate = RateWithCI(rate=0.90, ci_low=0.85, ci_high=0.95, n=94)
    baseline = _row("gen_base", kappa=PanelKappa(kappa=0.72, ci_low=0.60, ci_high=0.81, n_items=345), guard=rate)
    candidate = _row("gen_new", kappa=PanelKappa(kappa=0.30, ci_low=0.15, ci_high=0.45, n_items=345), guard=rate)

    report = check_instrument(candidate, baseline)
    assert report.checked is True
    assert report.degraded is True
    assert len(report.findings) == 1
    message = report.findings[0].message
    assert "0.30" in message and "0.72" in message  # both kappas named
    assert "345" in message  # n named, never a bare "agreement fell"


def test_overlapping_kappa_intervals_do_not_trigger_instrument_degraded() -> None:
    """Same one-sided, CI-aware rule as the rate check: the candidate's entire
    interval must sit below the baseline's point estimate. A nominally lower
    kappa whose interval still reaches the baseline is noise — kappa's bootstrap
    CI on this corpus is [0.227, 0.730] wide, so a point-estimate comparison
    would fire almost every run."""
    baseline = _row("gen_base", kappa=PanelKappa(kappa=0.53, ci_low=0.23, ci_high=0.73, n_items=345))
    candidate = _row("gen_new", kappa=PanelKappa(kappa=0.48, ci_low=0.20, ci_high=0.68, n_items=345))
    report = check_instrument(candidate, baseline)
    assert report.checked is True
    assert report.degraded is False
    assert report.findings == ()


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------


def test_a_rising_kappa_never_fires() -> None:
    baseline = _row("gen_base", kappa=PanelKappa(kappa=0.50, ci_low=0.30, ci_high=0.70, n_items=345))
    candidate = _row("gen_new", kappa=PanelKappa(kappa=0.80, ci_low=0.70, ci_high=0.90, n_items=345))
    assert check_instrument(candidate, baseline).degraded is False


def test_a_missing_kappa_on_either_side_is_reported_as_unchecked_not_as_stable() -> None:
    """A single-judge run records no panel kappa. Silently reporting 'stable'
    would claim an instrument check that never happened."""
    baseline = _row("gen_base", kappa=PanelKappa(kappa=0.72, ci_low=0.60, ci_high=0.81, n_items=345))
    candidate = _row("gen_new", kappa=None)
    report = check_instrument(candidate, baseline)
    assert report.checked is False
    assert report.degraded is False
    assert report.skip_reason


def test_a_kappa_without_an_interval_is_unchecked_rather_than_point_compared() -> None:
    """A point-estimate comparison is the exact trap DEC-185 records. A kappa
    recorded without its bootstrap CI cannot be gated on at all."""
    baseline = _row("gen_base", kappa=PanelKappa(kappa=0.72, ci_low=None, ci_high=None, n_items=345))
    candidate = _row("gen_new", kappa=PanelKappa(kappa=0.10, ci_low=None, ci_high=None, n_items=345))
    report = check_instrument(candidate, baseline)
    assert report.checked is False
    assert report.degraded is False


# ---------------------------------------------------------------------------
# format_instrument_report
# ---------------------------------------------------------------------------


def test_format_distinguishes_stable_degraded_and_skipped() -> None:
    stable = _row("gen_new", kappa=PanelKappa(kappa=0.72, ci_low=0.60, ci_high=0.81, n_items=345))
    base = _row("gen_base", kappa=PanelKappa(kappa=0.70, ci_low=0.58, ci_high=0.80, n_items=345))
    assert "STABLE" in format_instrument_report(check_instrument(stable, base))

    dropped = _row("gen_new", kappa=PanelKappa(kappa=0.20, ci_low=0.10, ci_high=0.30, n_items=345))
    assert "DEGRADED" in format_instrument_report(check_instrument(dropped, base))

    unchecked = _row("gen_new", kappa=None)
    assert "SKIPPED" in format_instrument_report(check_instrument(unchecked, base))
