"""
Module: test_sequence_records
Layer: test (unit)
Purpose: Tests for evals/sequence_records.py — frozen Pydantic v2 schema for
         multi-turn sequence transcripts: SequenceRun, Repetition, Turn, and
         supporting models (ResetReceipt, SequenceRunConfig).
Dependencies: pytest, pydantic, sequence_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sequence_records import (
    Repetition,
    ResetReceipt,
    SequenceRun,
    SequenceRunConfig,
    Turn,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_RECEIPT = ResetReceipt(
    cleared=("graph_nodes", "emotion_store", "session_cache"),
    surviving=("tick_counter",),
    duration_ms=120,
)

_TURN = Turn(
    index=0,
    actor="player",
    message="Hello",
    response="Hi there.",
    world_epoch=1,
    tick=42,
    retrieved_context=(),
    duration_ms=800,
)


def _make_turns(n: int) -> tuple[Turn, ...]:
    return tuple(
        Turn(
            index=i,
            actor="player" if i % 2 == 0 else "mira_innkeeper",
            message=f"msg_{i}",
            response=f"resp_{i}",
            world_epoch=1,
            tick=i,
            retrieved_context=(),
            duration_ms=500 + i,
        )
        for i in range(n)
    )


def _make_repetition(index: int, n_turns: int = 5) -> Repetition:
    return Repetition(
        index=index,
        reset_receipt=_RECEIPT,
        turns=_make_turns(n_turns),
    )


def _make_run(k: int = 3, n_turns: int = 5) -> SequenceRun:
    return SequenceRun(
        run_id="run_001",
        scenario_id="gossip_chain",
        k=k,
        config=SequenceRunConfig(
            generation_model="qwen2.5:7b",
            git_sha="abc1234",
        ),
        repetitions=tuple(_make_repetition(i, n_turns) for i in range(k)),
    )


# ---------------------------------------------------------------------------
# RED anchor: missing reset_receipt must raise
# ---------------------------------------------------------------------------


def test_repetition_without_a_reset_receipt_raises() -> None:
    """Creating a Repetition without a reset_receipt raises ValidationError."""
    with pytest.raises(ValidationError):
        Repetition(index=0, turns=())  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Round-trip: 3 repetitions, 5 turns each
# ---------------------------------------------------------------------------


def test_three_repetition_five_turn_run_round_trips() -> None:
    """A SequenceRun with 3 repetitions and 5 turns round-trips through JSON."""
    run = _make_run(k=3, n_turns=5)
    serialized = run.model_dump_json()
    restored = SequenceRun.model_validate_json(serialized)
    assert restored == run


def test_round_trip_preserves_repetition_count() -> None:
    """All 3 repetitions survive JSON round-trip."""
    run = _make_run(k=3)
    restored = SequenceRun.model_validate_json(run.model_dump_json())
    assert len(restored.repetitions) == 3


def test_round_trip_preserves_turn_count() -> None:
    """All 5 turns per repetition survive JSON round-trip."""
    run = _make_run(k=1, n_turns=5)
    restored = SequenceRun.model_validate_json(run.model_dump_json())
    assert len(restored.repetitions[0].turns) == 5


def test_round_trip_preserves_reset_receipt() -> None:
    """reset_receipt content is preserved through JSON round-trip."""
    run = _make_run(k=1, n_turns=1)
    restored = SequenceRun.model_validate_json(run.model_dump_json())
    receipt = restored.repetitions[0].reset_receipt
    assert receipt.cleared == ("graph_nodes", "emotion_store", "session_cache")
    assert receipt.surviving == ("tick_counter",)
    assert receipt.duration_ms == 120


# ---------------------------------------------------------------------------
# Frozen: no in-place mutation allowed
# ---------------------------------------------------------------------------


def test_sequence_run_is_frozen() -> None:
    """SequenceRun is immutable — attribute assignment raises."""
    run = _make_run()
    with pytest.raises(Exception):
        run.k = 99  # type: ignore[misc]


def test_repetition_is_frozen() -> None:
    """Repetition is immutable — attribute assignment raises."""
    rep = _make_repetition(0)
    with pytest.raises(Exception):
        rep.index = 99  # type: ignore[misc]


def test_turn_is_frozen() -> None:
    """Turn is immutable — attribute assignment raises."""
    with pytest.raises(Exception):
        _TURN.tick = 99  # type: ignore[misc]


def test_reset_receipt_is_frozen() -> None:
    """ResetReceipt is immutable — attribute assignment raises."""
    with pytest.raises(Exception):
        _RECEIPT.duration_ms = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Field presence: no field the harness cannot populate
# ---------------------------------------------------------------------------


def test_turn_fields_are_present() -> None:
    """Turn carries all required fields from the schema specification."""
    turn = _TURN
    assert hasattr(turn, "index")
    assert hasattr(turn, "actor")
    assert hasattr(turn, "message")
    assert hasattr(turn, "response")
    assert hasattr(turn, "world_epoch")
    assert hasattr(turn, "tick")
    assert hasattr(turn, "retrieved_context")
    assert hasattr(turn, "duration_ms")


def test_repetition_fields_are_present() -> None:
    """Repetition carries all required fields from the schema specification."""
    rep = _make_repetition(0)
    assert hasattr(rep, "index")
    assert hasattr(rep, "reset_receipt")
    assert hasattr(rep, "turns")


def test_sequence_run_fields_are_present() -> None:
    """SequenceRun carries all required fields from the schema specification."""
    run = _make_run()
    assert hasattr(run, "run_id")
    assert hasattr(run, "scenario_id")
    assert hasattr(run, "k")
    assert hasattr(run, "config")
    assert hasattr(run, "repetitions")


# ---------------------------------------------------------------------------
# reset_receipt independence evidence
# ---------------------------------------------------------------------------


def test_reset_receipt_cleared_is_a_tuple() -> None:
    """ResetReceipt.cleared is a tuple (immutable, ordered evidence)."""
    assert isinstance(_RECEIPT.cleared, tuple)


def test_reset_receipt_surviving_is_a_tuple() -> None:
    """ResetReceipt.surviving is a tuple."""
    assert isinstance(_RECEIPT.surviving, tuple)


def test_reset_receipt_duration_ms_is_non_negative() -> None:
    """ResetReceipt.duration_ms is non-negative."""
    assert _RECEIPT.duration_ms >= 0


def test_each_repetition_has_its_own_receipt() -> None:
    """Each Repetition in a SequenceRun holds its own reset_receipt."""
    run = _make_run(k=3)
    for rep in run.repetitions:
        assert rep.reset_receipt is not None


# ---------------------------------------------------------------------------
# k consistency
# ---------------------------------------------------------------------------


def test_sequence_run_k_matches_repetition_count() -> None:
    """SequenceRun.k equals the number of repetitions in a well-formed run."""
    run = _make_run(k=3)
    assert run.k == 3
    assert len(run.repetitions) == 3


def test_repetition_indices_are_sequential() -> None:
    """Repetition indices in a well-formed run are 0, 1, ..., k-1."""
    run = _make_run(k=4)
    assert [r.index for r in run.repetitions] == [0, 1, 2, 3]
