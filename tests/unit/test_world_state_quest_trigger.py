"""
Tests for WorldStateQuestTrigger — unit tests only (no Neo4j, no LLM).

All external dependencies are mocked via unittest.mock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.quest_generation.world_state_quest_trigger import (
    WorldStateQuestTrigger,
)
from npc_engine.world.world_state import WorldState


def _make_world_state(epoch: str = "war", active_conditions: list[str] | None = None) -> WorldState:
    """Return a WorldState fixture with the given epoch."""
    return WorldState(epoch=epoch, active_conditions=active_conditions or [])


def _make_generated_quest(quest_id: str = "q-001") -> MagicMock:
    """Return a minimal mock that looks like a GeneratedQuest."""
    quest = MagicMock()
    quest.quest_id = quest_id
    return quest


@pytest.mark.asyncio
async def test_run_tick_calls_generate_once_for_war_epoch() -> None:
    """run_tick should call generate exactly once when epoch is 'war' and a military NPC exists."""
    mock_session = AsyncMock()
    mock_engine = AsyncMock()
    generated = _make_generated_quest("q-001")
    mock_engine.generate.return_value = generated

    with (
        patch(
            "npc_engine.engines.quest_generation.world_state_quest_trigger.get_world_state",
            new=AsyncMock(return_value=_make_world_state(epoch="war")),
        ),
        patch(
            "npc_engine.engines.quest_generation.world_state_quest_trigger.get_any_military_npc",
            new=AsyncMock(return_value="captain_sorn"),
        ),
    ):
        trigger = WorldStateQuestTrigger(generation_engine=mock_engine)
        result = await trigger.run_tick(session=mock_session, tick_id="t1")

    mock_engine.generate.assert_called_once_with(
        mock_session,
        quest_giver_id="captain_sorn",
    )
    assert result["quests_created"] == 1
    assert result["quest_ids"] == ["q-001"]
    assert result["tick_id"] == "t1"


@pytest.mark.asyncio
async def test_run_tick_idempotent_same_tick() -> None:
    """run_tick called twice with the same tick_id should call generate only on the first call."""
    mock_session = AsyncMock()
    mock_engine = AsyncMock()
    generated = _make_generated_quest("q-002")
    mock_engine.generate.return_value = generated

    with (
        patch(
            "npc_engine.engines.quest_generation.world_state_quest_trigger.get_world_state",
            new=AsyncMock(return_value=_make_world_state(epoch="war")),
        ),
        patch(
            "npc_engine.engines.quest_generation.world_state_quest_trigger.get_any_military_npc",
            new=AsyncMock(return_value="captain_sorn"),
        ),
    ):
        trigger = WorldStateQuestTrigger(generation_engine=mock_engine)
        first = await trigger.run_tick(session=mock_session, tick_id="t1")
        second = await trigger.run_tick(session=mock_session, tick_id="t1")

    # generate must be called only once across both tick calls
    assert mock_engine.generate.call_count == 1
    assert first["quests_created"] == 1
    assert second["quests_created"] == 0


@pytest.mark.asyncio
async def test_run_tick_different_ticks_call_generate_twice() -> None:
    """run_tick with distinct tick_ids should call generate on each distinct tick."""
    mock_session = AsyncMock()
    mock_engine = AsyncMock()
    mock_engine.generate.return_value = _make_generated_quest("q-003")

    with (
        patch(
            "npc_engine.engines.quest_generation.world_state_quest_trigger.get_world_state",
            new=AsyncMock(return_value=_make_world_state(epoch="war")),
        ),
        patch(
            "npc_engine.engines.quest_generation.world_state_quest_trigger.get_any_military_npc",
            new=AsyncMock(return_value="captain_sorn"),
        ),
    ):
        trigger = WorldStateQuestTrigger(generation_engine=mock_engine)
        await trigger.run_tick(session=mock_session, tick_id="t1")
        await trigger.run_tick(session=mock_session, tick_id="t2")

    assert mock_engine.generate.call_count == 2


@pytest.mark.asyncio
async def test_run_tick_no_npc_skips_generate() -> None:
    """run_tick should return quests_created=0 when no suitable NPC is found."""
    mock_session = AsyncMock()
    mock_engine = AsyncMock()

    with (
        patch(
            "npc_engine.engines.quest_generation.world_state_quest_trigger.get_world_state",
            new=AsyncMock(return_value=_make_world_state(epoch="war")),
        ),
        patch(
            "npc_engine.engines.quest_generation.world_state_quest_trigger.get_any_military_npc",
            new=AsyncMock(return_value=None),
        ),
    ):
        trigger = WorldStateQuestTrigger(generation_engine=mock_engine)
        result = await trigger.run_tick(session=mock_session, tick_id="t1")

    mock_engine.generate.assert_not_called()
    assert result["quests_created"] == 0


@pytest.mark.asyncio
async def test_run_tick_unknown_epoch_skips_generate() -> None:
    """run_tick for an epoch with no mapping should return quests_created=0."""
    mock_session = AsyncMock()
    mock_engine = AsyncMock()

    with patch(
        "npc_engine.engines.quest_generation.world_state_quest_trigger.get_world_state",
        new=AsyncMock(return_value=_make_world_state(epoch="age_of_peace")),
    ):
        trigger = WorldStateQuestTrigger(generation_engine=mock_engine)
        result = await trigger.run_tick(session=mock_session, tick_id="t1")

    mock_engine.generate.assert_not_called()
    assert result["quests_created"] == 0


@pytest.mark.asyncio
async def test_run_tick_generate_raises_value_error_handled() -> None:
    """run_tick should return quests_created=0 when generate raises ValueError."""
    mock_session = AsyncMock()
    mock_engine = AsyncMock()
    mock_engine.generate.side_effect = ValueError("no template for archetype")

    with (
        patch(
            "npc_engine.engines.quest_generation.world_state_quest_trigger.get_world_state",
            new=AsyncMock(return_value=_make_world_state(epoch="war")),
        ),
        patch(
            "npc_engine.engines.quest_generation.world_state_quest_trigger.get_any_military_npc",
            new=AsyncMock(return_value="captain_sorn"),
        ),
    ):
        trigger = WorldStateQuestTrigger(generation_engine=mock_engine)
        result = await trigger.run_tick(session=mock_session, tick_id="t1")

    assert result["quests_created"] == 0
    assert result["quest_ids"] == []
