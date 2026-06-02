"""
Tests for engines.quest_generation.event_quest_trigger and
graph.event_trigger_queries.

Covers:
- No trigger events → 0 quests, no generate() calls
- Military NPC at event location → quest created with cause_event_id
- No NPC at location, fallback to any military NPC → quest still created
- No military NPC anywhere → 0 quests, warning logged
- generate() raises ValueError (pacing suppression) → graceful skip
- Multiple unprocessed events → multiple quests
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.quest_generation.event_quest_trigger import (
    DEFAULT_MILITARY_ARCHETYPES,
    DEFAULT_TRIGGER_EVENT_TYPES,
    EventQuestTrigger,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_generated_quest(quest_id: str = "quest-001") -> MagicMock:
    q = MagicMock()
    q.quest_id = quest_id
    return q


# ---------------------------------------------------------------------------
# No trigger events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_no_events_returns_zero_quests() -> None:
    session = AsyncMock()
    engine = AsyncMock()

    with patch(
        "npc_engine.engines.quest_generation.event_quest_trigger.get_unprocessed_trigger_events",
        new_callable=AsyncMock,
        return_value=[],
    ):
        trigger = EventQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=1)

    assert result["quests_created"] == 0
    assert result["quest_ids"] == []
    engine.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Military NPC at event location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_npc_at_location_creates_quest() -> None:
    session = AsyncMock()
    engine = AsyncMock()
    engine.generate.return_value = _make_generated_quest("q-1")

    with (
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_unprocessed_trigger_events",
            new_callable=AsyncMock,
            return_value=[{"event_id": "evt-1", "location_id": "loc-barracks"}],
        ),
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_military_npc_at_location",
            new_callable=AsyncMock,
            return_value="captain_sorn",
        ),
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_any_military_npc",
            new_callable=AsyncMock,
        ) as mock_fallback,
    ):
        trigger = EventQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=5)

    assert result["quests_created"] == 1
    assert result["quest_ids"] == ["q-1"]
    engine.generate.assert_awaited_once_with(
        session,
        quest_giver_id="captain_sorn",
        cause_event_id="evt-1",
    )
    mock_fallback.assert_not_called()


# ---------------------------------------------------------------------------
# Fallback to any military NPC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_fallback_to_any_military_npc() -> None:
    session = AsyncMock()
    engine = AsyncMock()
    engine.generate.return_value = _make_generated_quest("q-2")

    with (
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_unprocessed_trigger_events",
            new_callable=AsyncMock,
            return_value=[{"event_id": "evt-2", "location_id": "loc-market"}],
        ),
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_military_npc_at_location",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_any_military_npc",
            new_callable=AsyncMock,
            return_value="general_vorrath",
        ),
    ):
        trigger = EventQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=5)

    assert result["quests_created"] == 1
    engine.generate.assert_awaited_once_with(
        session,
        quest_giver_id="general_vorrath",
        cause_event_id="evt-2",
    )


# ---------------------------------------------------------------------------
# No military NPC anywhere
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_no_military_npc_skips_event() -> None:
    session = AsyncMock()
    engine = AsyncMock()

    with (
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_unprocessed_trigger_events",
            new_callable=AsyncMock,
            return_value=[{"event_id": "evt-3", "location_id": "loc-tavern"}],
        ),
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_military_npc_at_location",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_any_military_npc",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        trigger = EventQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=7)

    assert result["quests_created"] == 0
    engine.generate.assert_not_called()


# ---------------------------------------------------------------------------
# generate() raises ValueError (pacing suppression or missing template)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_generate_value_error_is_skipped() -> None:
    session = AsyncMock()
    engine = AsyncMock()
    engine.generate.side_effect = ValueError("Quest generation suppressed by pacing engine")

    with (
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_unprocessed_trigger_events",
            new_callable=AsyncMock,
            return_value=[{"event_id": "evt-4", "location_id": "loc-barracks"}],
        ),
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_military_npc_at_location",
            new_callable=AsyncMock,
            return_value="captain_sorn",
        ),
    ):
        trigger = EventQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=9)

    assert result["quests_created"] == 0
    assert result["quest_ids"] == []


# ---------------------------------------------------------------------------
# Multiple events → multiple quests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_multiple_events_creates_multiple_quests() -> None:
    session = AsyncMock()
    engine = AsyncMock()
    engine.generate.side_effect = [
        _make_generated_quest("q-10"),
        _make_generated_quest("q-11"),
    ]

    events = [
        {"event_id": "evt-10", "location_id": "loc-barracks"},
        {"event_id": "evt-11", "location_id": "loc-barracks"},
    ]

    with (
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_unprocessed_trigger_events",
            new_callable=AsyncMock,
            return_value=events,
        ),
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_military_npc_at_location",
            new_callable=AsyncMock,
            return_value="captain_sorn",
        ),
    ):
        trigger = EventQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=10)

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
    trigger = EventQuestTrigger(
        generation_engine=engine,
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
    session = AsyncMock()
    engine = AsyncMock()
    engine.generate.return_value = _make_generated_quest("q-20")

    with (
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_unprocessed_trigger_events",
            new_callable=AsyncMock,
            return_value=[{"event_id": "evt-20", "location_id": None}],
        ),
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_military_npc_at_location",
            new_callable=AsyncMock,
        ) as mock_loc,
        patch(
            "npc_engine.engines.quest_generation.event_quest_trigger.get_any_military_npc",
            new_callable=AsyncMock,
            return_value="captain_sorn",
        ),
    ):
        trigger = EventQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=12)

    mock_loc.assert_not_called()
    assert result["quests_created"] == 1
