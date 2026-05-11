"""
test_schedule_service.py - Unit tests for ScheduleService operations.

Does NOT: connect to Neo4j or any external service. All graph calls are mocked.

Dependencies injected: None.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.schedule_service import ScheduleService
from npc_engine.utils.errors import ScheduleAssignmentError, ScheduleNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a MagicMock that behaves like an AsyncSession."""
    session = MagicMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    session.begin_transaction = AsyncMock(return_value=tx)
    return session


def _make_service(session=None) -> tuple[ScheduleService, MagicMock]:
    session = session or _make_session()
    return ScheduleService(session=session), session


# ---------------------------------------------------------------------------
# create_schedule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_schedule_returns_properties():
    service, _ = _make_service()
    entries = [{"time_of_day": "morning", "location_id": "loc_1", "activity": "patrol"}]

    with patch("npc_engine.graph.schedule_service.upsert_schedule", new_callable=AsyncMock) as mock_upsert:
        result = await service.create_schedule(
            schedule_id="sched_1",
            name="Guard Shift",
            description="Morning patrol",
            entries=entries,
        )

    mock_upsert.assert_awaited_once()
    assert result["id"] == "sched_1"
    assert result["name"] == "Guard Shift"
    parsed = json.loads(result["entries"])
    assert parsed[0]["time_of_day"] == "morning"


@pytest.mark.asyncio
async def test_create_schedule_rejects_invalid_time_of_day():
    service, _ = _make_service()
    with pytest.raises(ValueError, match="Invalid time_of_day"):
        await service.create_schedule(
            schedule_id="sched_bad",
            name="Bad",
            description=None,
            entries=[{"time_of_day": "dawn", "location_id": "loc_1"}],
        )


# ---------------------------------------------------------------------------
# assign_schedule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assign_schedule_calls_writer():
    service, _ = _make_service()
    with patch("npc_engine.graph.schedule_service.assign_schedule", new_callable=AsyncMock) as mock_assign:
        await service.assign_schedule(character_id="char_1", schedule_id="sched_1")
    mock_assign.assert_awaited_once_with(
        mock_assign.call_args[0][0],  # tx
        character_id="char_1",
        schedule_id="sched_1",
    )


@pytest.mark.asyncio
async def test_assign_schedule_propagates_error():
    service, _ = _make_service()
    err = ScheduleAssignmentError(
        character_id="char_x",
        schedule_id="sched_x",
        detail="Character or Schedule node not found",
    )
    with patch("npc_engine.graph.schedule_service.assign_schedule", new_callable=AsyncMock, side_effect=err):
        with pytest.raises(ScheduleAssignmentError):
            await service.assign_schedule(character_id="char_x", schedule_id="sched_x")


# ---------------------------------------------------------------------------
# get_schedule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_schedule_returns_dict():
    service, _ = _make_service()
    fake = {"id": "sched_1", "name": "Guard Shift", "entries": "[]"}
    with patch("npc_engine.graph.schedule_service.get_schedule", new_callable=AsyncMock, return_value=fake):
        result = await service.get_schedule("sched_1")
    assert result["id"] == "sched_1"


@pytest.mark.asyncio
async def test_get_schedule_raises_when_not_found():
    service, _ = _make_service()
    with patch("npc_engine.graph.schedule_service.get_schedule", new_callable=AsyncMock, return_value=None):
        with pytest.raises(ScheduleNotFoundError):
            await service.get_schedule("missing")


# ---------------------------------------------------------------------------
# get_character_location_at
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_character_location_at_valid():
    service, _ = _make_service()
    with patch(
        "npc_engine.graph.schedule_service.get_character_location_at",
        new_callable=AsyncMock,
        return_value="loc_tavern",
    ):
        result = await service.get_character_location_at("char_1", "evening")
    assert result == "loc_tavern"


@pytest.mark.asyncio
async def test_get_character_location_at_invalid_time_raises():
    service, _ = _make_service()
    with pytest.raises(ValueError, match="Invalid time_of_day"):
        await service.get_character_location_at("char_1", "noon")


@pytest.mark.asyncio
async def test_get_character_location_at_returns_none_when_no_schedule():
    service, _ = _make_service()
    with patch(
        "npc_engine.graph.schedule_service.get_character_location_at",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await service.get_character_location_at("char_1", "morning")
    assert result is None


# ---------------------------------------------------------------------------
# get_characters_at_location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_characters_at_location_valid():
    service, _ = _make_service()
    with patch(
        "npc_engine.graph.schedule_service.get_characters_at_location",
        new_callable=AsyncMock,
        return_value=["char_1", "char_2"],
    ):
        result = await service.get_characters_at_location("loc_market", "midday")
    assert result == ["char_1", "char_2"]


@pytest.mark.asyncio
async def test_get_characters_at_location_invalid_time_raises():
    service, _ = _make_service()
    with pytest.raises(ValueError, match="Invalid time_of_day"):
        await service.get_characters_at_location("loc_1", "dusk")


@pytest.mark.asyncio
async def test_get_characters_at_location_returns_empty():
    service, _ = _make_service()
    with patch(
        "npc_engine.graph.schedule_service.get_characters_at_location",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await service.get_characters_at_location("loc_empty", "night")
    assert result == []


# ---------------------------------------------------------------------------
# unassign_schedule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unassign_schedule_calls_writer():
    service, _ = _make_service()
    with patch("npc_engine.graph.schedule_service.unassign_schedule", new_callable=AsyncMock) as mock_unassign:
        await service.unassign_schedule(character_id="char_1")
    mock_unassign.assert_awaited_once()
    _, kwargs = mock_unassign.call_args
    assert kwargs["character_id"] == "char_1"


# ---------------------------------------------------------------------------
# get_character_schedule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_character_schedule_returns_schedule_when_assigned():
    service, _ = _make_service()
    fake = {"id": "sched_1", "name": "Day Patrol", "entries": "[]"}
    with patch(
        "npc_engine.graph.schedule_service.get_character_schedule",
        new_callable=AsyncMock,
        return_value=fake,
    ):
        result = await service.get_character_schedule("char_1")
    assert result is not None
    assert result["id"] == "sched_1"


@pytest.mark.asyncio
async def test_get_character_schedule_returns_none_when_unassigned():
    service, _ = _make_service()
    with patch(
        "npc_engine.graph.schedule_service.get_character_schedule",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await service.get_character_schedule("char_no_schedule")
    assert result is None


# ---------------------------------------------------------------------------
# create_schedule — additional coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_schedule_with_full_five_slot_schedule():
    """All five valid time_of_day values accepted in a single schedule."""
    service, _ = _make_service()
    entries = [
        {"time_of_day": "morning",   "location_id": "loc_1", "activity": "patrol"},
        {"time_of_day": "midday",    "location_id": "loc_2", "activity": "lunch"},
        {"time_of_day": "afternoon", "location_id": "loc_2", "activity": "patrol"},
        {"time_of_day": "evening",   "location_id": "loc_3", "activity": "dinner"},
        {"time_of_day": "night",     "location_id": "loc_1", "activity": "sleep"},
    ]
    with patch("npc_engine.graph.schedule_service.upsert_schedule", new_callable=AsyncMock):
        result = await service.create_schedule(
            schedule_id="sched_full",
            name="Full Day",
            description="All five slots",
            entries=entries,
        )
    parsed = json.loads(result["entries"])
    assert len(parsed) == 5
    assert {e["time_of_day"] for e in parsed} == {"morning", "midday", "afternoon", "evening", "night"}


@pytest.mark.asyncio
async def test_create_schedule_allows_entries_without_activity():
    """Entries without an 'activity' key are valid (activity is optional)."""
    service, _ = _make_service()
    entries = [{"time_of_day": "morning", "location_id": "loc_1"}]
    with patch("npc_engine.graph.schedule_service.upsert_schedule", new_callable=AsyncMock):
        result = await service.create_schedule(
            schedule_id="sched_no_activity",
            name="Minimal",
            description=None,
            entries=entries,
        )
    parsed = json.loads(result["entries"])
    assert parsed[0].get("activity") is None


@pytest.mark.asyncio
async def test_create_schedule_rejects_second_invalid_entry():
    """Validation fails even if the first entry is valid and only the second is invalid."""
    service, _ = _make_service()
    entries = [
        {"time_of_day": "morning", "location_id": "loc_1"},
        {"time_of_day": "dusk",    "location_id": "loc_2"},  # invalid
    ]
    with pytest.raises(ValueError, match="Invalid time_of_day"):
        await service.create_schedule(
            schedule_id="sched_mixed",
            name="Mixed",
            description=None,
            entries=entries,
        )
