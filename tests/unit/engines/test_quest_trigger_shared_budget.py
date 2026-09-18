"""
Module: test_quest_trigger_shared_budget
Layer: tests/unit
Purpose: RED anchor for T7.2 (L11-03, SEV-03) — three quest triggers sharing one
         TickLLMBudget must not exceed the per-tick invocation cap when firing at
         maximum capacity.
Does NOT: perform I/O, touch Neo4j, or use real LLM. The quest generation engine
    uses a mock LLM adapter; all graph ports are mocked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.config import QUEST_TRIGGER_MAX_LLM_INVOCATIONS_PER_TICK
from npc_engine.engines.quest_generation.event_quest_trigger import EventQuestTrigger
from npc_engine.engines.quest_generation.need_quest_trigger import NeedQuestTrigger
from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine
from npc_engine.engines.quest_generation.slot_models import QuestTemplateRecord, SlotDefinition
from npc_engine.engines.quest_generation.tick_llm_budget import TickLLMBudget
from npc_engine.engines.quest_generation.world_state_quest_trigger import WorldStateQuestTrigger
from npc_engine.world.world_state import WorldState

# Maximum LLM calls a single generate() can make:
# _MAX_RETRIES=3 slot-fill attempts (mock returns {} → all fail validation) + 1 flavor call.
_CALLS_PER_INVOCATION: int = 4

_TICK_ID: int = 1
_PROMPTS_DIR: Path = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "src" / "npc_engine" / "prompts" / "quest_generation"
)


def _make_template() -> QuestTemplateRecord:
    """Minimal template with one item slot."""
    return QuestTemplateRecord(
        id="fetch_item_v1",
        name="Fetch Item",
        archetype="guard_captain",
        severity=20,
        slot_definitions=(SlotDefinition(name="item", node_type="item", required=True),),
        description_template="Retrieve {item} from somewhere.",
        reward_template="10 gold coins",
    )


def _make_quest_gen_repo() -> Any:
    """Mock QuestGenerationGraphPort that supplies minimal data for generate()."""
    repo = MagicMock()
    repo.get_world_state_day_and_rate = AsyncMock(return_value=(1, 1.0))
    repo.get_world_state_context = AsyncMock(return_value={"epoch": "war", "active_conditions": []})
    repo.get_character_info = AsyncMock(return_value=("guard_captain", "Sorn"))
    repo.get_giver_context = AsyncMock(return_value={
        "goals": [], "beliefs": [], "mood": "neutral", "mood_intensity": 0,
        "needs": [], "inventory": [], "location": "barracks", "faction": [],
    })
    # item-001 satisfies the item slot — returned as the only candidate.
    repo.get_candidate_ids_by_label = AsyncMock(return_value=["item-001"])
    repo.check_node_labels = AsyncMock(return_value=["Item"])
    repo.get_template_skill_requirements = AsyncMock(return_value=[])
    repo.check_skill_threshold = AsyncMock(return_value=True)
    repo.create_quest = AsyncMock()
    repo.record_causation = AsyncMock()
    return repo


def _make_llm_mock(call_counter: list[int]) -> Any:
    """Mock LLMStructuredProtocol that always returns {} — forces all slot-fill retries."""

    async def _generate_structured(
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        system: str = "",
    ) -> dict[str, Any]:
        call_counter[0] += 1
        # Return empty dict: slot-fill validation fails (no required fills).
        # Flavor call also gets {}, which causes fallback to description_template.
        return {}

    mock_llm = MagicMock()
    mock_llm.generate_structured = _generate_structured
    return mock_llm


def _make_event_trigger_repo(n_events: int = 10) -> Any:
    """Mock EventTriggerGraphPort returning n_events unprocessed events."""
    events = [{"event_id": f"evt-{i:03d}", "location_id": f"loc-{i:03d}"} for i in range(n_events)]
    repo = MagicMock()
    repo.get_unprocessed_trigger_events = AsyncMock(return_value=events)
    # Each location has a distinct military NPC so no invocation is skipped.
    async def _military_at_location(*, location_id: str, archetypes: frozenset[str]) -> str | None:
        idx = location_id.split("-")[-1]
        return f"npc-{idx}"
    repo.get_military_npc_at_location = _military_at_location
    repo.get_any_military_npc = AsyncMock(return_value="npc-999")
    repo.has_draft_quest = AsyncMock(return_value=False)
    return repo


def _make_need_trigger_repo(n_needs: int = 10) -> Any:
    """Mock NeedTriggerGraphPort returning n_needs needs below threshold."""
    needs = [
        {"character_id": f"npc-{i:03d}", "kind": "food", "level": 10}
        for i in range(n_needs)
    ]
    repo = MagicMock()
    repo.get_all_needs_below_threshold = AsyncMock(return_value=needs)
    repo.has_draft_quest = AsyncMock(return_value=False)
    return repo


def _make_world_state_trigger_repo() -> Any:
    """Mock EventTriggerGraphPort for WorldStateQuestTrigger (one military NPC, no draft)."""
    repo = MagicMock()
    repo.get_any_military_npc = AsyncMock(return_value="npc-ws-001")
    repo.has_draft_quest = AsyncMock(return_value=False)
    return repo


def _make_world_state_repo() -> Any:
    """Mock WorldStateGraphPort returning a 'war' epoch world state."""
    repo = MagicMock()
    repo.get_world_state = AsyncMock(return_value=WorldState(epoch="war", active_conditions=[]))
    return repo


@pytest.mark.asyncio
async def test_three_triggers_respect_shared_llm_budget() -> None:
    """Without a shared budget, all three triggers fire at max → 40+ LLM calls today (RED).

    After T7.2 the shared TickLLMBudget limits total invocations to
    QUEST_TRIGGER_MAX_LLM_INVOCATIONS_PER_TICK, so total LLM calls are at most
    QUEST_TRIGGER_MAX_LLM_INVOCATIONS_PER_TICK * _CALLS_PER_INVOCATION (L11-03, SEV-03).
    """
    call_counter: list[int] = [0]
    mock_llm = _make_llm_mock(call_counter)
    repo = _make_quest_gen_repo()
    gen_engine = QuestGenerationEngine(
        llm_client=mock_llm,
        templates=[_make_template()],
        prompts_dir=_PROMPTS_DIR,
        quest_gen_repo=repo,
        slot_validation_repo=repo,
    )

    # All three triggers share the same budget — this is what the test verifies.
    budget = TickLLMBudget(max_invocations=QUEST_TRIGGER_MAX_LLM_INVOCATIONS_PER_TICK)

    event_trigger = EventQuestTrigger(
        generation_engine=gen_engine,
        trigger_repo=_make_event_trigger_repo(n_events=10),
        llm_budget=budget,
    )
    need_trigger = NeedQuestTrigger(
        generation_engine=gen_engine,
        need_trigger_repo=_make_need_trigger_repo(n_needs=10),
        llm_budget=budget,
    )
    ws_trigger = WorldStateQuestTrigger(
        generation_engine=gen_engine,
        world_state_repo=_make_world_state_repo(),
        trigger_repo=_make_world_state_trigger_repo(),
        llm_budget=budget,
    )

    await event_trigger.run_tick(tick_id=_TICK_ID)
    await need_trigger.run_tick(tick_id=_TICK_ID)
    await ws_trigger.run_tick(tick_id=_TICK_ID)

    total = call_counter[0]
    cap = QUEST_TRIGGER_MAX_LLM_INVOCATIONS_PER_TICK * _CALLS_PER_INVOCATION
    assert total <= cap, (
        f"Total LLM adapter calls {total} exceeds shared cap {cap} "
        f"(= {QUEST_TRIGGER_MAX_LLM_INVOCATIONS_PER_TICK} invocations × "
        f"{_CALLS_PER_INVOCATION} calls each). "
        "The three quest triggers must share a TickLLMBudget that caps total invocations "
        "to QUEST_TRIGGER_MAX_LLM_INVOCATIONS_PER_TICK per tick (T7.2, L11-03, SEV-03)."
    )
