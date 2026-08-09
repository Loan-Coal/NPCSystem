"""
Module: test_sequence_runner
Layer: test (unit)
Purpose: Tests for evals/sequence_runner.py — k-repetition sequence running with
         reset between runs, per-repetition recording, and CaseStat aggregation.
Dependencies: pytest, sequence_runner (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from sequence_runner import RepetitionRecord, SequenceResult, run_sequence


# ---------------------------------------------------------------------------
# RED anchor: reset call discipline
# ---------------------------------------------------------------------------


def test_reset_is_called_between_every_repetition() -> None:
    """With k=3, reset is called exactly 3 times and never after the last run."""
    call_order: list[str] = []

    def reset_fn() -> None:
        call_order.append("reset")

    def scenario_fn() -> bool:
        call_order.append("run")
        return True

    run_sequence("scenario_x", scenario_fn, reset_fn, k=3)

    assert call_order.count("reset") == 3
    assert call_order[-1] == "run", "reset must not be called after the last repetition"
    assert call_order == ["reset", "run", "reset", "run", "reset", "run"]


# ---------------------------------------------------------------------------
# Exception isolation
# ---------------------------------------------------------------------------


def test_failed_repetition_does_not_abort_sequence() -> None:
    """A mid-run exception records a failed repetition without aborting the set."""
    call_count = 0

    def scenario_fn() -> bool:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("mid-run failure")
        return True

    result = run_sequence("scenario_x", scenario_fn, lambda: None, k=3)

    assert len(result.repetitions) == 3
    assert result.repetitions[0].passed is True
    assert result.repetitions[1].passed is False
    assert result.repetitions[1].error is not None
    assert "mid-run failure" in (result.repetitions[1].error or "")
    assert result.repetitions[2].passed is True


def test_failed_repetition_error_message_captured() -> None:
    """The exception message is stored verbatim in error."""
    def scenario_fn() -> bool:
        raise ValueError("unique_error_marker_abc123")

    result = run_sequence("scenario_x", scenario_fn, lambda: None, k=1)

    assert result.repetitions[0].error == "unique_error_marker_abc123"


# ---------------------------------------------------------------------------
# Repetition indexing
# ---------------------------------------------------------------------------


def test_repetition_indices_are_zero_based_and_sequential() -> None:
    """Each RepetitionRecord carries the correct zero-based repetition index."""
    result = run_sequence("scenario_x", lambda: True, lambda: None, k=4)

    for i, rec in enumerate(result.repetitions):
        assert rec.repetition == i


def test_repetition_count_matches_k() -> None:
    """SequenceResult.repetitions has exactly k entries."""
    result = run_sequence("scenario_x", lambda: True, lambda: None, k=5)
    assert len(result.repetitions) == 5


# ---------------------------------------------------------------------------
# CaseStat aggregation
# ---------------------------------------------------------------------------


def test_stat_pass_count_matches_repetition_outcomes() -> None:
    """CaseStat.passes equals the number of True-returning repetitions."""
    call_count = 0

    def scenario_fn() -> bool:
        nonlocal call_count
        call_count += 1
        return call_count % 2 == 1  # alternates True/False

    result = run_sequence("scenario_x", scenario_fn, lambda: None, k=4)
    # 4 runs: True, False, True, False → 2 passes
    assert result.stat.passes == 2
    assert result.stat.k == 4


def test_stat_scenario_id_matches_input() -> None:
    """CaseStat.case_id equals the scenario_id passed to run_sequence."""
    result = run_sequence("scenario_gossip_chain", lambda: True, lambda: None, k=1)
    assert result.stat.case_id == "scenario_gossip_chain"


def test_stat_classification_stable_pass_all_pass() -> None:
    """All repetitions passing → classification is stable_pass."""
    result = run_sequence("scenario_x", lambda: True, lambda: None, k=3)
    assert result.stat.classification == "stable_pass"


def test_stat_classification_stable_fail_all_fail() -> None:
    """All repetitions failing → classification is stable_fail."""
    result = run_sequence("scenario_x", lambda: False, lambda: None, k=3)
    assert result.stat.classification == "stable_fail"


def test_stat_classification_flaky_mixed() -> None:
    """Mixed pass/fail → classification is flaky."""
    outcomes = iter([True, False, True])

    def scenario_fn() -> bool:
        return next(outcomes)

    result = run_sequence("scenario_x", scenario_fn, lambda: None, k=3)
    assert result.stat.classification == "flaky"


# ---------------------------------------------------------------------------
# SequenceResult fields
# ---------------------------------------------------------------------------


def test_sequence_result_scenario_id() -> None:
    """SequenceResult.scenario_id echoes the input."""
    result = run_sequence("scenario_grief_persistence", lambda: True, lambda: None, k=1)
    assert result.scenario_id == "scenario_grief_persistence"


def test_sequence_result_k_field() -> None:
    """SequenceResult.k echoes the requested repetition count."""
    result = run_sequence("scenario_x", lambda: True, lambda: None, k=7)
    assert result.k == 7


def test_sequence_result_is_immutable() -> None:
    """SequenceResult is frozen — attribute assignment raises TypeError."""
    result = run_sequence("scenario_x", lambda: True, lambda: None, k=1)
    with pytest.raises(Exception):
        result.k = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Reset cost recorded
# ---------------------------------------------------------------------------


def test_reset_cost_ms_is_non_negative() -> None:
    """Every RepetitionRecord records a non-negative reset_cost_ms."""
    result = run_sequence("scenario_x", lambda: True, lambda: None, k=3)
    for rec in result.repetitions:
        assert rec.reset_cost_ms >= 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_k_zero_raises_value_error() -> None:
    """k=0 is invalid and raises ValueError."""
    with pytest.raises(ValueError):
        run_sequence("scenario_x", lambda: True, lambda: None, k=0)


def test_k_negative_raises_value_error() -> None:
    """k<0 is invalid and raises ValueError."""
    with pytest.raises(ValueError):
        run_sequence("scenario_x", lambda: True, lambda: None, k=-1)
