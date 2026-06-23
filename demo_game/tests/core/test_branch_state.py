"""
Module: test_branch_state
Layer: demo_game (tests)
Purpose: Unit tests for BranchState immutability, JSON round-trip, and
         save/load persistence. No I/O against a real filesystem except via tmp_path.
Dependencies: demo_game.branches.branch_state, pathlib, pytest
Used by: make test-demo
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo_game.branches.branch_state import (
    BranchState,
    ChoiceRecord,
    load_branch_state,
    save_branch_state,
)


# ---------------------------------------------------------------------------
# ChoiceRecord
# ---------------------------------------------------------------------------


def test_choice_record_to_dict_round_trip() -> None:
    """ChoiceRecord serialises and deserialises without loss."""
    record = ChoiceRecord(branch_id="branch_a", option_index=1, label="Option B")
    assert ChoiceRecord.from_dict(record.to_dict()) == record


def test_choice_record_from_dict_missing_key_raises() -> None:
    """ChoiceRecord.from_dict raises KeyError on incomplete dict."""
    with pytest.raises(KeyError):
        ChoiceRecord.from_dict({"branch_id": "x", "option_index": 0})


# ---------------------------------------------------------------------------
# BranchState — immutability
# ---------------------------------------------------------------------------


def test_branch_state_starts_empty() -> None:
    """Fresh BranchState has no choices."""
    state = BranchState()
    assert state.choices == ()


def test_with_choice_returns_new_instance() -> None:
    """with_choice does not mutate original; returns a new BranchState."""
    original = BranchState()
    updated = original.with_choice("branch_a", 0, "Spare")
    assert original.choices == ()
    assert len(updated.choices) == 1


def test_with_choice_appends_in_order() -> None:
    """Multiple with_choice calls preserve insertion order."""
    state = BranchState()
    state = state.with_choice("branch_a", 0, "Spare")
    state = state.with_choice("branch_b", 1, "Betray")
    assert [c.branch_id for c in state.choices] == ["branch_a", "branch_b"]


def test_has_chosen_true_after_recording() -> None:
    """has_chosen returns True for a branch that was recorded."""
    state = BranchState().with_choice("branch_a", 0, "Spare")
    assert state.has_chosen("branch_a") is True


def test_has_chosen_false_for_unrecorded() -> None:
    """has_chosen returns False for a branch not yet chosen."""
    state = BranchState().with_choice("branch_a", 0, "Spare")
    assert state.has_chosen("branch_b") is False


def test_choice_for_returns_record() -> None:
    """choice_for returns the correct ChoiceRecord for a known branch_id."""
    state = BranchState().with_choice("branch_garrick", 1, "Turn in")
    record = state.choice_for("branch_garrick")
    assert record is not None
    assert record.option_index == 1
    assert record.label == "Turn in"


def test_choice_for_returns_none_if_absent() -> None:
    """choice_for returns None when branch_id has not been chosen."""
    state = BranchState()
    assert state.choice_for("branch_garrick") is None


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


def test_to_json_produces_valid_json() -> None:
    """to_json produces parseable JSON with a version field."""
    state = BranchState().with_choice("branch_a", 0, "Spare")
    payload = json.loads(state.to_json())
    assert "version" in payload
    assert "choices" in payload
    assert len(payload["choices"]) == 1


def test_from_json_round_trip() -> None:
    """to_json/from_json round-trip preserves all choices."""
    original = (
        BranchState()
        .with_choice("branch_a", 0, "Spare")
        .with_choice("branch_b", 1, "Betray")
    )
    restored = BranchState.from_json(original.to_json())
    assert restored.choices == original.choices


def test_from_json_empty_state() -> None:
    """from_json handles an empty choices list."""
    state = BranchState.from_json('{"version": 1, "choices": []}')
    assert state.choices == ()


def test_from_json_invalid_json_raises() -> None:
    """from_json raises ValueError on malformed JSON."""
    with pytest.raises(ValueError, match="Cannot deserialise"):
        BranchState.from_json("not json at all")


def test_from_json_missing_key_raises() -> None:
    """from_json raises ValueError when a required key is missing from a record."""
    bad_json = json.dumps({"version": 1, "choices": [{"branch_id": "x"}]})
    with pytest.raises(ValueError, match="Cannot deserialise"):
        BranchState.from_json(bad_json)


# ---------------------------------------------------------------------------
# save / load
# ---------------------------------------------------------------------------


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    """save_branch_state and load_branch_state are inverse operations."""
    path = tmp_path / "branch_state.json"
    state = BranchState().with_choice("branch_garrick", 0, "Spare")
    save_branch_state(state, path=path)
    loaded = load_branch_state(path=path)
    assert loaded.choices == state.choices


def test_load_returns_empty_state_if_file_absent(tmp_path: Path) -> None:
    """load_branch_state returns empty BranchState when the file does not exist."""
    path = tmp_path / "nonexistent.json"
    state = load_branch_state(path=path)
    assert state.choices == ()


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    """save_branch_state creates parent directories if they do not exist."""
    path = tmp_path / "nested" / "deep" / "state.json"
    state = BranchState().with_choice("branch_a", 0, "X")
    save_branch_state(state, path=path)
    assert path.exists()


def test_load_returns_empty_on_corrupt_file(tmp_path: Path) -> None:
    """load_branch_state returns empty state on corrupt JSON (graceful fallback)."""
    path = tmp_path / "corrupt.json"
    path.write_text("{{invalid", encoding="utf-8")
    state = load_branch_state(path=path)
    assert state.choices == ()
