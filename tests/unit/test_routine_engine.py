"""
test_routine_engine.py - Unit tests for RoutineEngine.

Does NOT: connect to Neo4j or any external service. All graph calls are mocked.

Dependencies injected: None.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.routine.routine_engine import RoutineEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a MagicMock that behaves like an AsyncSession."""
    session = MagicMock()
    session.run = AsyncMock()
    return session


def _make_engine() -> RoutineEngine:
    return RoutineEngine()


def _single(value) -> AsyncMock:
    """Return a mock result whose .single() returns value."""
    result = AsyncMock()
    result.single = AsyncMock(return_value=value)
    return result


def _cursor(rows: list[dict]) -> AsyncMock:
    """Return a mock result that async-iterates over rows."""

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def __aiter__(self):
            return self._iter()

        async def _iter(self):
            for row in self._rows:
                yield _FakeRecord(row)

    class _FakeRecord:
        def __init__(self, data):
            self._data = data

        def __getitem__(self, key):
            return self._data[key]

        def data(self):
            return self._data

    result = AsyncMock()
    result.__aiter__ = _FakeResult(rows).__aiter__
    result.__anext__ = _FakeResult(rows).__aiter__().__anext__

    async_result = MagicMock()
    async_result.__aiter__ = _FakeResult(rows).__aiter__

    return async_result


# ---------------------------------------------------------------------------
# Factories for common record shapes
# ---------------------------------------------------------------------------


def _char_record(
    char_id: str,
    entries: list[dict],
    current_loc: str | None,
    routine_override: dict | None = None,
) -> dict:
    return {
        "character_id": char_id,
        "entries_json": json.dumps(entries),
        "current_location_id": current_loc,
        "routine_override": json.dumps(routine_override) if routine_override else None,
    }


# ---------------------------------------------------------------------------
# Tests: character moves when schedule says new location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_character_moves_to_scheduled_location():
    engine = _make_engine()
    session = _make_session()

    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    rows = [_char_record("char_a", entries, current_loc="loc_barracks")]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=10)

    mock_update.assert_awaited_once_with(
        session=session, character_id="char_a", location_id="loc_market"
    )
    assert result["moved"] == 1
    assert result["skipped"] == 0


# ---------------------------------------------------------------------------
# Tests: character stays when already at scheduled location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_character_stays_when_already_at_location():
    engine = _make_engine()
    session = _make_session()

    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    rows = [_char_record("char_a", entries, current_loc="loc_market")]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=10)

    mock_update.assert_not_awaited()
    assert result["moved"] == 0
    assert result["skipped"] == 0


# ---------------------------------------------------------------------------
# Tests: character skipped when no matching schedule entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_character_skipped_when_no_matching_entry():
    engine = _make_engine()
    session = _make_session()

    entries = [{"time_of_day": "evening", "location_id": "loc_tavern"}]
    rows = [_char_record("char_a", entries, current_loc="loc_market")]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=10)

    mock_update.assert_not_awaited()
    assert result["skipped"] == 1
    assert result["moved"] == 0


# ---------------------------------------------------------------------------
# Tests: routine_override non-null and not expired → override location used
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_not_expired_uses_override_location():
    engine = _make_engine()
    session = _make_session()

    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    override = {"location_id": "loc_home", "expires_at_tick": 20}
    rows = [_char_record("char_a", entries, current_loc="loc_barracks", routine_override=override)]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
        patch(
            "npc_engine.engines.routine.routine_engine.clear_routine_override",
            new_callable=AsyncMock,
        ) as mock_clear,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=10)

    mock_update.assert_awaited_once_with(
        session=session, character_id="char_a", location_id="loc_home"
    )
    mock_clear.assert_not_awaited()
    assert result["moved"] == 1


# ---------------------------------------------------------------------------
# Tests: routine_override expired → cleared, schedule location used
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_expired_clears_and_uses_schedule():
    engine = _make_engine()
    session = _make_session()

    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    override = {"location_id": "loc_home", "expires_at_tick": 5}
    rows = [_char_record("char_a", entries, current_loc="loc_barracks", routine_override=override)]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
        patch(
            "npc_engine.engines.routine.routine_engine.clear_routine_override",
            new_callable=AsyncMock,
        ) as mock_clear,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=10)

    mock_clear.assert_awaited_once_with(session=session, character_id="char_a")
    mock_update.assert_awaited_once_with(
        session=session, character_id="char_a", location_id="loc_market"
    )
    assert result["moved"] == 1


# ---------------------------------------------------------------------------
# Tests: return dict always has moved and skipped keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_result_always_has_moved_and_skipped():
    engine = _make_engine()
    session = _make_session()

    with patch(
        "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=1)

    assert "moved" in result
    assert "skipped" in result


# ---------------------------------------------------------------------------
# Tests: multiple characters, mixed results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_characters_mixed_results():
    engine = _make_engine()
    session = _make_session()

    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    rows = [
        _char_record("char_a", entries, current_loc="loc_barracks"),   # moves
        _char_record("char_b", entries, current_loc="loc_market"),     # stays
        _char_record("char_c", [{"time_of_day": "night", "location_id": "loc_home"}], current_loc="loc_market"),  # skipped
    ]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=5)

    assert result["moved"] == 1
    assert result["skipped"] == 1
    mock_update.assert_awaited_once_with(
        session=session, character_id="char_a", location_id="loc_market"
    )


# ---------------------------------------------------------------------------
# Tests: malformed entries JSON — character skipped gracefully
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_entries_json_skips_character():
    engine = _make_engine()
    session = _make_session()

    rows = [{"character_id": "char_x", "entries_json": "not-valid-json", "current_location_id": "loc_a", "routine_override": None}]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=1)

    mock_update.assert_not_awaited()
    assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# Tests: override at exact expiry tick is treated as expired
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_at_exact_expiry_tick_clears_and_uses_schedule():
    """tick_id == expires_at_tick means the override has expired (condition is strictly <)."""
    engine = _make_engine()
    session = _make_session()

    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    override = {"location_id": "loc_home", "expires_at_tick": 10}
    rows = [_char_record("char_a", entries, current_loc="loc_home", routine_override=override)]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
        patch(
            "npc_engine.engines.routine.routine_engine.clear_routine_override",
            new_callable=AsyncMock,
        ) as mock_clear,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=10)

    mock_clear.assert_awaited_once_with(session=session, character_id="char_a")
    mock_update.assert_awaited_once_with(
        session=session, character_id="char_a", location_id="loc_market"
    )
    assert result["moved"] == 1


# ---------------------------------------------------------------------------
# Tests: override JSON malformed — falls back to schedule entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_malformed_json_falls_back_to_schedule():
    engine = _make_engine()
    session = _make_session()

    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    # Produce a record with invalid (non-JSON) override string directly
    rows = [{
        "character_id": "char_a",
        "entries_json": json.dumps(entries),
        "current_location_id": "loc_barracks",
        "routine_override": "not-valid-json",
    }]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
        patch(
            "npc_engine.engines.routine.routine_engine.clear_routine_override",
            new_callable=AsyncMock,
        ) as mock_clear,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=5)

    mock_clear.assert_not_awaited()
    mock_update.assert_awaited_once_with(
        session=session, character_id="char_a", location_id="loc_market"
    )
    assert result["moved"] == 1


# ---------------------------------------------------------------------------
# Tests: character already at override location — no move
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_character_already_at_override_location_no_move():
    engine = _make_engine()
    session = _make_session()

    entries = [{"time_of_day": "morning", "location_id": "loc_market"}]
    override = {"location_id": "loc_home", "expires_at_tick": 20}
    rows = [_char_record("char_a", entries, current_loc="loc_home", routine_override=override)]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=5)

    mock_update.assert_not_awaited()
    assert result["moved"] == 0
    assert result["skipped"] == 0


# ---------------------------------------------------------------------------
# Tests: character with null entries_json — skipped (no schedule)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_character_with_null_entries_json_skips():
    engine = _make_engine()
    session = _make_session()

    rows = [{
        "character_id": "char_y",
        "entries_json": None,
        "current_location_id": "loc_a",
        "routine_override": None,
    }]

    with (
        patch(
            "npc_engine.engines.routine.routine_engine.get_scheduled_characters",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.routine.routine_engine.update_character_location",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        result = await engine.run_tick(session=session, time_of_day="morning", tick_id=1)

    mock_update.assert_not_awaited()
    assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# Tests: _entry_location static method — direct coverage
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
