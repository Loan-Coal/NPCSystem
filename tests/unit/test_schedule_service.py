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
