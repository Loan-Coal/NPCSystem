"""
Module: test_sequence_rates
Layer: test (unit)
Purpose: Tests for evals/sequence_rates.py — fidelity-conditional report rendering
         and pooled order-effect computation. Pure logic only; the live orchestration
         (run_all_sequences) requires the seeded stack and is exercised in the
         EVAL-P12.4 live run, not here.
Dependencies: pytest, sequence_rates (evals/), sequence_runner (evals/),
              sequence_fidelity (evals/), sequence_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from sequence_fidelity import SequenceStat
from sequence_order_effect import order_effect_check
from sequence_rates import _format_metrics_summary, _format_stat_line, pooled_order_effect, render_report
from sequence_records import ResetReceipt
from sequence_runner import RepetitionRecord, SequenceResult

_FULL_RECEIPT = ResetReceipt(cleared=("world_state.epoch",), surviving=(), duration_ms=1)
_PARTIAL_RECEIPT = ResetReceipt(
    cleared=("world_state.epoch",), surviving=("emotion_store",), duration_ms=1
)


def _result(scenario_id: str, outcomes: tuple[bool, ...], receipt: ResetReceipt) -> SequenceResult:
    """Build a SequenceResult fixture from a tuple of per-repetition outcomes."""
    k = len(outcomes)
    reps = tuple(
        RepetitionRecord(repetition=i, passed=passed, duration_ms=1, reset_receipt=receipt)
        for i, passed in enumerate(outcomes)
    )
    passes = sum(outcomes)
    from sequence_fidelity import sequence_stat

    stat = sequence_stat(scenario_id, passes, tuple(r.reset_receipt for r in reps))
    return SequenceResult(scenario_id=scenario_id, k=k, repetitions=reps, stat=stat)


# ---------------------------------------------------------------------------
# RED anchor: every rate carries k and fidelity tier adjacent to it
# ---------------------------------------------------------------------------


def test_scenario_rate_carries_k_and_fidelity_tier() -> None:
    """Both FULL and PARTIAL rendered lines name k and the fidelity tier explicitly."""
    full_result = _result("scenario_reputation_drift", (True, True, True), _FULL_RECEIPT)
    partial_result = _result("scenario_gossip_chain", (True, False, True), _PARTIAL_RECEIPT)

    report = render_report(
        [full_result, partial_result],
        order_effect=pooled_order_effect([full_result, partial_result]),
    )

    assert "scenario_reputation_drift reaches 3/3 (k=3, FULL)" in report
    assert "scenario_gossip_chain reaches 2/3 (k=3, PARTIAL" in report


# ---------------------------------------------------------------------------
# Negative test, both branches (ROADMAP validation requirement): forcing PARTIAL
# removes the interval from the rendered output.
# ---------------------------------------------------------------------------


def test_forcing_partial_fidelity_removes_interval_from_rendered_output() -> None:
    """A fixture with fidelity forced to PARTIAL never prints a Wilson interval."""
    full_stat = SequenceStat(
        scenario_id="scenario_x", k=3, passes=3, pass_rate=1.0, fidelity="FULL",
        interval=(0.29, 1.0), classification="stable_pass", surviving=(),
    )
    partial_stat = full_stat.model_copy(update={
        "fidelity": "PARTIAL", "interval": None, "surviving": ("emotion_store",),
    })

    full_line = render_report(
        [SequenceResult(scenario_id="scenario_x", k=3, repetitions=(), stat=full_stat)], None
    )
    partial_line = render_report(
        [SequenceResult(scenario_id="scenario_x", k=3, repetitions=(), stat=partial_stat)],
        order_effect=order_effect_check([(True, True, False)]),
    )

    assert "[" in full_line and "]" in full_line  # interval bracket present at FULL
    assert "[" not in partial_line.splitlines()[0]  # no interval on the PARTIAL scenario line
    assert "CI withheld" in partial_line
    assert "ORDER EFFECT CHECK" in partial_line


def test_partial_without_order_effect_raises() -> None:
    """A PARTIAL run must never render with neither an interval nor the order-effect check."""
    partial_result = _result("scenario_x", (True, False), _PARTIAL_RECEIPT)
    with pytest.raises(ValueError):
        render_report([partial_result], order_effect=None)


# ---------------------------------------------------------------------------
# pooled_order_effect
# ---------------------------------------------------------------------------


def test_pooled_order_effect_builds_matrix_from_all_scenarios() -> None:
    """pooled_order_effect stacks every scenario's repetition outcomes into one matrix."""
    results = [
        _result("scenario_a", (True, True, False), _PARTIAL_RECEIPT),
        _result("scenario_b", (True, False, False), _PARTIAL_RECEIPT),
    ]
    result = pooled_order_effect(results)
    assert result.rates_by_repetition == (1.0, 0.5, 0.0)


# ---------------------------------------------------------------------------
# render_report: all-FULL run needs no order-effect check
# ---------------------------------------------------------------------------


def test_all_full_run_renders_without_order_effect_block() -> None:
    """When every scenario is FULL, no order-effect block is required or printed."""
    result = _result("scenario_x", (True, True, True), _FULL_RECEIPT)
    report = render_report([result], order_effect=None)
    assert "ORDER EFFECT CHECK" not in report


# ---------------------------------------------------------------------------
# metrics_summary rendering (measurement-remediation Phase 3)
# ---------------------------------------------------------------------------


def test_format_metrics_summary_empty_returns_empty_string() -> None:
    """No metrics_summary -> no suffix, so existing scenario report lines are untouched."""
    assert _format_metrics_summary({}) == ""


def test_format_metrics_summary_renders_sorted_keys() -> None:
    """Multiple keys render sorted by name, three-decimal formatted."""
    rendered = _format_metrics_summary({"reach": 0.5, "hops": 2.0})
    assert rendered == " | metrics: hops=2.000, reach=0.500"


def test_format_stat_line_appends_metrics_at_full_fidelity() -> None:
    """A FULL-fidelity stat with metrics_summary prints both the interval and the metrics."""
    stat = SequenceStat(
        scenario_id="gossip", k=3, passes=3, pass_rate=1.0, fidelity="FULL",
        interval=(0.29, 1.0), classification="stable_pass", surviving=(),
        metrics_summary={"hops": 2.0},
    )
    line = _format_stat_line(stat)
    assert "[0.290, 1.000]" in line
    assert "metrics: hops=2.000" in line


def test_format_stat_line_appends_metrics_at_partial_fidelity() -> None:
    """A PARTIAL-fidelity stat still appends metrics_summary after the withheld-CI text."""
    stat = SequenceStat(
        scenario_id="gossip", k=3, passes=2, pass_rate=2 / 3, fidelity="PARTIAL",
        interval=None, classification="flaky", surviving=("emotion_store",),
        metrics_summary={"hops": 1.5},
    )
    line = _format_stat_line(stat)
    assert "CI withheld" in line
    assert "metrics: hops=1.500" in line
