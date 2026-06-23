"""
Tests for engines.quest_generation.event_quest_trigger.

Covers:
- No trigger events → 0 quests, no generate() calls
- Military NPC at event location → quest created with cause_event_id
- No NPC at location, fallback to any military NPC → quest still created
- No military NPC anywhere → 0 quests, warning logged
- generate() raises ValueError (pacing suppression) → graceful skip
- Multiple unprocessed events → multiple quests
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.quest_generation.event_quest_trigger import (
    DEFAULT_MILITARY_ARCHETYPES,
    DEFAULT_TRIGGER_EVENT_TYPES,
    EventQuestTrigger,
)


def _make_trigger_repo(
    events: list | None = None,
    npc_at_location: str | None = None,
    any_military_npc: str | None = None,
) -> MagicMock:
    """Return a mock EventTriggerGraphPort."""
    repo = MagicMock()
    repo.get_unprocessed_trigger_events = AsyncMock(return_value=events or [])
    repo.get_military_npc_at_location = AsyncMock(return_value=npc_at_location)
    repo.get_any_military_npc = AsyncMock(return_value=any_military_npc)
    return repo


def _make_generated_quest(quest_id: str = "quest-001") -> MagicMock:
    q = MagicMock()
    q.quest_id = quest_id
    return q


# ---------------------------------------------------------------------------
# No trigger events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_no_events_returns_zero_quests() -> None:
    engine = AsyncMock()
    trigger_repo = _make_trigger_repo(events=[])

    trigger = EventQuestTrigger(generation_engine=engine, trigger_repo=trigger_repo)
    result = await trigger.run_tick(tick_id=1)

    assert result["quests_created"] == 0
    assert result["quest_ids"] == []
    engine.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Military NPC at event location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_npc_at_location_creates_quest() -> None:
    engine = AsyncMock()
    engine.generate.return_value = _make_generated_quest("q-1")

    trigger_repo = _make_trigger_repo(
        events=[{"event_id": "evt-1", "location_id": "loc-barracks"}],
        npc_at_location="captain_sorn",
    )
    trigger = EventQuestTrigger(generation_engine=engine, trigger_repo=trigger_repo)
    result = await trigger.run_tick(tick_id=5)

    assert result["quests_created"] == 1
    assert result["quest_ids"] == ["q-1"]
    engine.generate.assert_awaited_once_with(
        quest_giver_id="captain_sorn",
        cause_event_id="evt-1",
    )
    trigger_repo.get_any_military_npc.assert_not_called()


# ---------------------------------------------------------------------------
# Fallback to any military NPC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_fallback_to_any_military_npc() -> None:
    engine = AsyncMock()
    engine.generate.return_value = _make_generated_quest("q-2")

    trigger_repo = _make_trigger_repo(
        events=[{"event_id": "evt-2", "location_id": "loc-market"}],
        npc_at_location=None,
        any_military_npc="general_vorrath",
    )
    trigger = EventQuestTrigger(generation_engine=engine, trigger_repo=trigger_repo)
    result = await trigger.run_tick(tick_id=5)

    assert result["quests_created"] == 1
    engine.generate.assert_awaited_once_with(
        quest_giver_id="general_vorrath",
        cause_event_id="evt-2",
    )


# ---------------------------------------------------------------------------
# No military NPC anywhere
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_no_military_npc_skips_event() -> None:
    engine = AsyncMock()

    trigger_repo = _make_trigger_repo(
        events=[{"event_id": "evt-3", "location_id": "loc-tavern"}],
        npc_at_location=None,
        any_military_npc=None,
    )
    trigger = EventQuestTrigger(generation_engine=engine, trigger_repo=trigger_repo)
    result = await trigger.run_tick(tick_id=7)

    assert result["quests_created"] == 0
    engine.generate.assert_not_called()


# ---------------------------------------------------------------------------
# generate() raises ValueError (pacing suppression or missing template)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_generate_value_error_is_skipped() -> None:
    engine = AsyncMock()
    engine.generate.side_effect = ValueError("Quest generation suppressed by pacing engine")

    trigger_repo = _make_trigger_repo(
        events=[{"event_id": "evt-4", "location_id": "loc-barracks"}],
        npc_at_location="captain_sorn",
    )
    trigger = EventQuestTrigger(generation_engine=engine, trigger_repo=trigger_repo)
    result = await trigger.run_tick(tick_id=9)

    assert result["quests_created"] == 0
    assert result["quest_ids"] == []


# ---------------------------------------------------------------------------
# Multiple events → multiple quests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_multiple_events_creates_multiple_quests() -> None:
    engine = AsyncMock()
    engine.generate.side_effect = [
        _make_generated_quest("q-10"),
        _make_generated_quest("q-11"),
    ]

    trigger_repo = _make_trigger_repo(
        events=[
            {"event_id": "evt-10", "location_id": "loc-barracks"},
            {"event_id": "evt-11", "location_id": "loc-barracks"},
        ],
        npc_at_location="captain_sorn",
    )
    trigger = EventQuestTrigger(generation_engine=engine, trigger_repo=trigger_repo)
    result = await trigger.run_tick(tick_id=10)

    assert result["quests_created"] == 2
    assert set(result["quest_ids"]) == {"q-10", "q-11"}


# ---------------------------------------------------------------------------
# Custom trigger types and archetypes
# ---------------------------------------------------------------------------


def test_default_constants_are_correct() -> None:
    assert "war_begins" in DEFAULT_TRIGGER_EVENT_TYPES
    assert "conflict" in DEFAULT_TRIGGER_EVENT_TYPES
    assert "guard_captain" in DEFAULT_MILITARY_ARCHETYPES


def test_constructor_accepts_custom_trigger_types() -> None:
    engine = AsyncMock()
    trigger_repo = _make_trigger_repo()
    trigger = EventQuestTrigger(
        generation_engine=engine,
        trigger_repo=trigger_repo,
        trigger_event_types=frozenset({"disaster"}),
        military_archetypes=frozenset({"warden"}),
    )
    assert trigger._trigger_event_types == frozenset({"disaster"})
    assert trigger._military_archetypes == frozenset({"warden"})


# ---------------------------------------------------------------------------
# Empty location_id falls back directly to any military NPC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_empty_location_skips_location_query() -> None:
    engine = AsyncMock()
    engine.generate.return_value = _make_generated_quest("q-20")

    trigger_repo = _make_trigger_repo(
        events=[{"event_id": "evt-20", "location_id": None}],
        npc_at_location=None,
        any_military_npc="captain_sorn",
    )
    trigger = EventQuestTrigger(generation_engine=engine, trigger_repo=trigger_repo)
    result = await trigger.run_tick(tick_id=12)

    trigger_repo.get_military_npc_at_location.assert_not_called()
    assert result["quests_created"] == 1
