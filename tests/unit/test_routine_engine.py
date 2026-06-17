"""
test_routine_engine.py - Unit tests for RoutineEngine.

Graph access is via a mocked RoutineGraphPort (DEC-122 / SEV-24); no session involved.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.routine.routine_engine import RoutineEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(rows: list[dict[str, Any]] | None = None) -> AsyncMock:
    """Return a mock RoutineGraphPort returning ``rows`` from get_scheduled_characters."""
    repo = AsyncMock()
    repo.get_scheduled_characters = AsyncMock(return_value=rows or [])
    repo.update_character_location = AsyncMock()
    repo.clear_routine_override = AsyncMock()
    repo.record_departure = AsyncMock()
    return repo


def _char_record(
    char_id: str,
    entries: list[dict],
    current_loc: str | None,
    routine_override: dict | None = None,
    current_arrived_at_tick: int | None = None,
) -> dict:
    return {
        "character_id": char_id,
        "entries_json": json.dumps(entries),
        "current_location_id": current_loc,
        "routine_override": json.dumps(routine_override) if routine_override else None,
        "current_arrived_at_tick": current_arrived_at_tick,
    }


# ---------------------------------------------------------------------------
# Movement behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_character_moves_to_scheduled_location():
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    repo = _make_repo([_char_record("char_a", entries, current_loc="loc_barracks")])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=10)

    repo.update_character_location.assert_awaited_once_with(
        character_id="char_a", location_id="loc_market", arrived_at_tick=10
    )
    assert result == {"moved": 1, "skipped": 0}


@pytest.mark.asyncio
async def test_character_stays_when_already_at_location():
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    repo = _make_repo([_char_record("char_a", entries, current_loc="loc_market")])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=10)

    repo.update_character_location.assert_not_awaited()
    assert result == {"moved": 0, "skipped": 0}


@pytest.mark.asyncio
async def test_character_skipped_when_no_matching_entry():
    entries = [{"time_of_day": "evening", "location_id": "loc_tavern"}]
    repo = _make_repo([_char_record("char_a", entries, current_loc="loc_market")])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=10)

    repo.update_character_location.assert_not_awaited()
    assert result == {"moved": 0, "skipped": 1}


@pytest.mark.asyncio
async def test_scheduler_session_kwarg_is_ignored():
    """The scheduler still passes session=...; the engine accepts and ignores it."""
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    repo = _make_repo([_char_record("char_a", entries, current_loc="loc_barracks")])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=10)

    assert result["moved"] == 1


# ---------------------------------------------------------------------------
# Routine override logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_not_expired_uses_override_location():
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    override = {"location_id": "loc_home", "expires_at_tick": 20}
    repo = _make_repo([_char_record("char_a", entries, current_loc="loc_barracks", routine_override=override)])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=10)

    repo.update_character_location.assert_awaited_once_with(
        character_id="char_a", location_id="loc_home", arrived_at_tick=10
    )
    repo.clear_routine_override.assert_not_awaited()
    assert result["moved"] == 1


@pytest.mark.asyncio
async def test_override_expired_clears_and_uses_schedule():
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    override = {"location_id": "loc_home", "expires_at_tick": 5}
    repo = _make_repo([_char_record("char_a", entries, current_loc="loc_barracks", routine_override=override)])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=10)

    repo.clear_routine_override.assert_awaited_once_with(character_id="char_a")
    repo.update_character_location.assert_awaited_once_with(
        character_id="char_a", location_id="loc_market", arrived_at_tick=10
    )
    assert result["moved"] == 1


@pytest.mark.asyncio
async def test_override_at_exact_expiry_tick_clears_and_uses_schedule():
    """tick_id == expires_at_tick means the override has expired (condition is strictly <)."""
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    override = {"location_id": "loc_home", "expires_at_tick": 10}
    repo = _make_repo([_char_record("char_a", entries, current_loc="loc_home", routine_override=override)])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=10)

    repo.clear_routine_override.assert_awaited_once_with(character_id="char_a")
    repo.update_character_location.assert_awaited_once_with(
        character_id="char_a", location_id="loc_market", arrived_at_tick=10
    )
    assert result["moved"] == 1


@pytest.mark.asyncio
async def test_override_malformed_json_falls_back_to_schedule():
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    repo = _make_repo([{
        "character_id": "char_a",
        "entries_json": json.dumps(entries),
        "current_location_id": "loc_barracks",
        "routine_override": "not-valid-json",
    }])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=5)

    repo.clear_routine_override.assert_not_awaited()
    repo.update_character_location.assert_awaited_once_with(
        character_id="char_a", location_id="loc_market", arrived_at_tick=5
    )
    assert result["moved"] == 1


@pytest.mark.asyncio
async def test_character_already_at_override_location_no_move():
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    override = {"location_id": "loc_home", "expires_at_tick": 20}
    repo = _make_repo([_char_record("char_a", entries, current_loc="loc_home", routine_override=override)])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=5)

    repo.update_character_location.assert_not_awaited()
    assert result == {"moved": 0, "skipped": 0}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_result_always_has_moved_and_skipped():
    engine = RoutineEngine(routine_repo=_make_repo([]))
    result = await engine.run_tick(time_of_day="morning", tick_id=1)
    assert "moved" in result
    assert "skipped" in result


@pytest.mark.asyncio
async def test_multiple_characters_mixed_results():
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    rows = [
        _char_record("char_a", entries, current_loc="loc_barracks"),   # moves
        _char_record("char_b", entries, current_loc="loc_market"),     # stays
        _char_record("char_c", [{"time_of_day": "night", "location_id": "loc_home"}], current_loc="loc_market"),  # skipped
    ]
    repo = _make_repo(rows)
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=5)

    assert result == {"moved": 1, "skipped": 1}
    repo.update_character_location.assert_awaited_once_with(
        character_id="char_a", location_id="loc_market", arrived_at_tick=5
    )


@pytest.mark.asyncio
async def test_malformed_entries_json_skips_character():
    repo = _make_repo([{
        "character_id": "char_x",
        "entries_json": "not-valid-json",
        "current_location_id": "loc_a",
        "routine_override": None,
    }])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=1)

    repo.update_character_location.assert_not_awaited()
    assert result["skipped"] == 1


@pytest.mark.asyncio
async def test_character_with_null_entries_json_skips():
    repo = _make_repo([{
        "character_id": "char_y",
        "entries_json": None,
        "current_location_id": "loc_a",
        "routine_override": None,
    }])
    engine = RoutineEngine(routine_repo=repo)

    result = await engine.run_tick(time_of_day="morning", tick_id=1)

    repo.update_character_location.assert_not_awaited()
    assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# ISSUE-014 — record_departure arrived_at_tick comes from the edge, not tick_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_departure_uses_arrived_at_tick_from_row():
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    repo = _make_repo([_char_record("char_a", entries, current_loc="loc_barracks", current_arrived_at_tick=3)])
    engine = RoutineEngine(routine_repo=repo)

    await engine.run_tick(time_of_day="morning", tick_id=10)

    repo.record_departure.assert_awaited_once()
    kwargs = repo.record_departure.call_args.kwargs
    assert kwargs["arrived_at_tick"] == 3   # from edge, not tick_id=10
    assert kwargs["departed_at_tick"] == 10


@pytest.mark.asyncio
async def test_record_departure_falls_back_to_tick_id_when_no_arrived_at_tick():
    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    repo = _make_repo([_char_record("char_a", entries, current_loc="loc_barracks", current_arrived_at_tick=None)])
    engine = RoutineEngine(routine_repo=repo)

    await engine.run_tick(time_of_day="morning", tick_id=10)

    kwargs = repo.record_departure.call_args.kwargs
    assert kwargs["arrived_at_tick"] == 10  # fallback: same as tick_id


# ---------------------------------------------------------------------------
# _entry_location static method — direct coverage (pure)
# ---------------------------------------------------------------------------


def test_entry_location_returns_none_for_none_json():
    assert RoutineEngine._entry_location(None, "morning") is None


def test_entry_location_returns_none_when_slot_not_in_entries():
    entries = json.dumps([{"time_of_day": "evening", "location_id": "loc_tavern"}])
    assert RoutineEngine._entry_location(entries, "morning") is None


def test_entry_location_returns_location_for_matching_slot():
    entries = json.dumps([
        {"time_of_day": "morning", "location_id": "loc_barracks"},
        {"time_of_day": "evening", "location_id": "loc_tavern"},
    ])
    assert RoutineEngine._entry_location(entries, "morning") == "loc_barracks"
    assert RoutineEngine._entry_location(entries, "evening") == "loc_tavern"


def test_entry_location_returns_none_for_malformed_json():
    assert RoutineEngine._entry_location("not-json", "morning") is None
