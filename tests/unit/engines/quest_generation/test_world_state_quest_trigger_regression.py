"""
Module: test_world_state_quest_trigger_regression
Layer: tests/unit
Purpose: Regression test for M1.1 — confirms that WorldStateQuestTrigger does not
         mint a new draft Quest on every tick when the NPC already has an outstanding
         draft. Before the fix, the trigger used only a tick-id sentinel which
         deduped identical tick_ids but not successive distinct ticks.
Does NOT: perform I/O, touch Neo4j, or call LLMs. All ports are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.quest_generation.world_state_quest_trigger import (
    WorldStateQuestTrigger,
)
from npc_engine.world.world_state import WorldState


def _war_world_state() -> WorldState:
    """Return a WorldState fixed at the 'war' epoch."""
    return WorldState(epoch="war", active_conditions=[])


def _make_generated_quest(quest_id: str = "q-reg-001") -> MagicMock:
    """Return a minimal mock that looks like a GeneratedQuest."""
    quest = MagicMock()
    quest.quest_id = quest_id
    return quest


@pytest.mark.asyncio
async def test_five_stable_ticks_generate_one_quest() -> None:
    """Five successive ticks under a stable 'war' epoch must mint exactly one quest.

    Before M1.1 the trigger minted one quest per tick because it used only a
    tick-id sentinel, which deduped the same tick_id fired twice but not
    successive distinct ticks.  After the fix an outstanding-draft guard mirrors
    need_quest_trigger.py:117 so ticks 2-5 skip generation for captain_sorn.
    """
    mock_engine = AsyncMock()
    mock_engine.generate.return_value = _make_generated_quest("q-reg-001")

    world_state_repo = MagicMock()
    world_state_repo.get_world_state = AsyncMock(return_value=_war_world_state())

    # First call: no draft exists → False. Subsequent calls: draft persists → True.
    _draft_check_count = 0

    async def _has_draft_quest(*, character_id: str) -> bool:
        nonlocal _draft_check_count
        already = _draft_check_count > 0
        _draft_check_count += 1
        return already

    trigger_repo = MagicMock()
    trigger_repo.get_any_military_npc = AsyncMock(return_value="captain_sorn")
    trigger_repo.has_draft_quest = _has_draft_quest

    trigger = WorldStateQuestTrigger(
        generation_engine=mock_engine,
        world_state_repo=world_state_repo,
        trigger_repo=trigger_repo,
    )

    total_created = 0
    for tick_num in range(1, 6):
        result = await trigger.run_tick(tick_id=f"t{tick_num}")
        total_created += result["quests_created"]

    assert mock_engine.generate.call_count == 1, (
        f"Expected exactly 1 quest generation across 5 ticks; "
        f"got {mock_engine.generate.call_count}. "
        "WorldStateQuestTrigger is minting a new quest per tick instead of "
        "respecting the outstanding-draft guard."
    )
    assert total_created == 1
