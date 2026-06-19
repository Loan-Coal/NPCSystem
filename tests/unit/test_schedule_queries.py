"""
Unit tests for npc_engine.graph.schedule_queries.

Covers all four public read functions:
- get_schedule: found / not found
- get_character_schedule: found / not found
- get_character_location_at: match / no-match time / no schedule / bad JSON
- get_characters_at_location: match / empty / bad JSON entry continues
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from npc_engine.graph.schedule_queries import (
    get_character_location_at,
    get_character_schedule,
    get_characters_at_location,
    get_schedule,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _aiter(*records):
    """Simulate a Neo4j async result stream."""
    for record in records:
        yield record


def _session_with_single(record) -> AsyncMock:
    """Return an AsyncMock session whose run().single() returns record."""
    result = AsyncMock()
    result.single = AsyncMock(return_value=record)
    session = AsyncMock()
    session.run = AsyncMock(return_value=result)
    return session


# ---------------------------------------------------------------------------
# get_schedule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_schedule_found() -> None:
    """get_schedule returns schedule properties when the node exists."""
    props = {"id": "sched_morning", "entries": "[]", "name": "morning_shift"}
    session = _session_with_single({"schedule": props})

    result = await get_schedule(session, schedule_id="sched_morning")

    assert result == props
    session.run.assert_awaited_once()
    _, kwargs = session.run.call_args
    assert kwargs.get("schedule_id") == "sched_morning" or "sched_morning" in session.run.call_args.args


@pytest.mark.asyncio
async def test_get_schedule_not_found() -> None:
    """get_schedule returns None when no node matches the id."""
    session = _session_with_single(None)

    result = await get_schedule(session, schedule_id="nonexistent")

    assert result is None


# ---------------------------------------------------------------------------
# get_character_schedule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_character_schedule_found() -> None:
    """get_character_schedule returns the schedule dict for a character that has one."""
    entries = json.dumps([{"time_of_day": "morning", "location_id": "market"}])
    props = {"id": "sched_aldric", "entries": entries}
    session = _session_with_single({"schedule": props})

    result = await get_character_schedule(session, character_id="aldric_merchant")

    assert result is not None
    assert result["id"] == "sched_aldric"


@pytest.mark.asyncio
async def test_get_character_schedule_not_assigned() -> None:
    """get_character_schedule returns None when the character has no FOLLOWS_SCHEDULE edge."""
    session = _session_with_single(None)

    result = await get_character_schedule(session, character_id="unscheduled_npc")

    assert result is None


# ---------------------------------------------------------------------------
# get_character_location_at
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_character_location_at_match() -> None:
    """Returns location_id when the time_of_day matches a schedule entry."""
    entries = json.dumps([
        {"time_of_day": "morning", "location_id": "market"},
        {"time_of_day": "evening", "location_id": "tavern"},
    ])
    session = _session_with_single({"entries_json": entries})

    result = await get_character_location_at(session, "aldric_merchant", "morning")

    assert result == "market"


@pytest.mark.asyncio
async def test_get_character_location_at_no_matching_time() -> None:
    """Returns None when no entry matches the requested time_of_day."""
    entries = json.dumps([{"time_of_day": "morning", "location_id": "market"}])
    session = _session_with_single({"entries_json": entries})

    result = await get_character_location_at(session, "aldric_merchant", "night")

    assert result is None


@pytest.mark.asyncio
async def test_get_character_location_at_no_schedule() -> None:
    """Returns None when the character has no schedule node."""
    session = _session_with_single(None)

    result = await get_character_location_at(session, "unscheduled_npc", "morning")

    assert result is None


@pytest.mark.asyncio
async def test_get_character_location_at_bad_json_returns_none() -> None:
    """Returns None when entries_json is not valid JSON."""
    session = _session_with_single({"entries_json": "not-json"})

    result = await get_character_location_at(session, "broken_npc", "morning")

    assert result is None


# ---------------------------------------------------------------------------
# get_characters_at_location
# ---------------------------------------------------------------------------


async def _session_with_aiter(*records) -> AsyncMock:
    """Return a session whose run() returns an async-iterable result."""
    session = AsyncMock()
    session.run = AsyncMock(return_value=_aiter(*records))
    return session


@pytest.mark.asyncio
async def test_get_characters_at_location_match() -> None:
    """Returns character IDs scheduled at the location for the time of day."""
    entries = json.dumps([{"time_of_day": "morning", "location_id": "market"}])
    record = {"character_id": "aldric_merchant", "entries_json": entries}
    session = await _session_with_aiter(record)

    result = await get_characters_at_location(session, "market", "morning")

    assert result == ["aldric_merchant"]


@pytest.mark.asyncio
async def test_get_characters_at_location_no_match_different_time() -> None:
    """Returns empty list when the location matches but the time_of_day does not."""
    entries = json.dumps([{"time_of_day": "morning", "location_id": "market"}])
    record = {"character_id": "aldric_merchant", "entries_json": entries}
    session = await _session_with_aiter(record)

    result = await get_characters_at_location(session, "market", "night")

    assert result == []


@pytest.mark.asyncio
async def test_get_characters_at_location_empty() -> None:
    """Returns empty list when there are no characters with schedules."""
    session = await _session_with_aiter()

    result = await get_characters_at_location(session, "market", "morning")

    assert result == []


@pytest.mark.asyncio
async def test_get_characters_at_location_bad_json_entry_skipped() -> None:
    """A character record with bad JSON entries_json is skipped; others still processed."""
    good_entries = json.dumps([{"time_of_day": "morning", "location_id": "market"}])
    bad_record = {"character_id": "broken_npc", "entries_json": "not-json"}
    good_record = {"character_id": "aldric_merchant", "entries_json": good_entries}
    session = await _session_with_aiter(bad_record, good_record)

    result = await get_characters_at_location(session, "market", "morning")

    assert result == ["aldric_merchant"]


@pytest.mark.asyncio
async def test_get_characters_at_location_multiple_matches() -> None:
    """Multiple characters at the same location + time are all returned."""
    entries_a = json.dumps([{"time_of_day": "morning", "location_id": "market"}])
    entries_b = json.dumps([
        {"time_of_day": "morning", "location_id": "market"},
        {"time_of_day": "evening", "location_id": "tavern"},
    ])
    session = await _session_with_aiter(
        {"character_id": "aldric_merchant", "entries_json": entries_a},
        {"character_id": "lira_fence", "entries_json": entries_b},
    )

    result = await get_characters_at_location(session, "market", "morning")

    assert set(result) == {"aldric_merchant", "lira_fence"}
