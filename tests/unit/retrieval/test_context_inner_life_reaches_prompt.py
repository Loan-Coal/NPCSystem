"""
Module: test_context_inner_life_reaches_prompt
Layer: tests/unit
Purpose: Regression tests for ISSUE-163 — the NPC's own inner state (beliefs, goals,
         memories) is written to the graph and ranked into tier A, then loses the
         scarce tier-A budget to items about the NPC's surroundings and never reaches
         the serialized prompt.
Dependencies: context_merger, context_scoring, context_budget_enforcer,
              context_serializer, context_config_models
Used by: pytest test runner
"""

from __future__ import annotations

import json
from typing import Any

from npc_engine.retrieval.context import ContextItem, MergedContext, fill_to_budget
from npc_engine.retrieval.context.context_merger import merge_context
from npc_engine.retrieval.context.context_scoring import rank_tier_items
from npc_engine.retrieval.context.context_utils import serialize_json
from npc_engine.schema.context_config_models import (
    LLMConfig,
    RelevanceWeights,
    TierBudgetTokens,
)

# Production-shaped: llm_config.yaml sets tier budgets far above the fraction-derived
# caps, so tier_a_fraction (0.55) of the 512-token prompt budget is what binds — the
# same 281-token tier-A cap the live engine runs under.
PRODUCTION_PROMPT_BUDGET = 512
PRODUCTION_TIER_A_BUDGET = 4000
PRODUCTION_TIER_B_BUDGET = 3000
PRODUCTION_TIER_C_BUDGET = 2000

# Raw pre-rank priorities emitted by the producers under test, kept in one place so the
# fixture cannot drift from subgraph_retriever / _build_tier_a_extended.
PRIORITY_CHARACTER = 100
PRIORITY_SESSION = 99
PRIORITY_LOCATION = 92
PRIORITY_NEARBY = 91
PRIORITY_MEMORIES = 90
PRIORITY_EVENT = 89
PRIORITY_BELIEFS = 88
PRIORITY_GOALS = 87

SEEDED_BELIEF_ID = "bel_mira_innkeeper_8ccbdbfd"
SEEDED_MEMORY_ID = "mem_mira_innkeeper_eastern_road"


def _llm_config() -> LLMConfig:
    """Return an LLMConfig carrying the shipped production weights and tier budgets."""
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(
            tier_a=PRODUCTION_TIER_A_BUDGET,
            tier_b=PRODUCTION_TIER_B_BUDGET,
            tier_c=PRODUCTION_TIER_C_BUDGET,
        ),
        session_turns_budget_tokens=1200,
        compression_trigger_ratio=0.85,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.30,
            severity=0.20,
            proximity=0.20,
            relation=0.20,
            quest=0.10,
        ),
    )


def _sized(marker: str, tokens: int) -> str:
    """Return a string estimating to exactly `tokens` tokens (4 chars per token)."""
    return marker * (tokens * 4)


def _seeded_belief() -> list[dict[str, Any]]:
    """One belief as get_beliefs_for_character returns it."""
    return [
        {
            "id": SEEDED_BELIEF_ID,
            "content": "The war will come here eventually.",
            "confidence": 70,
            "is_deception": False,
        }
    ]


def _seeded_memory() -> list[dict[str, Any]]:
    """One memory with vividness=0 — the value both demo-world memories carry."""
    return [
        {
            "id": SEEDED_MEMORY_ID,
            "content": "You asked about the eastern road and the bandits on it.",
            "vividness": 0,
            "emotional_charge": 48,
        }
    ]


def _tier_a_items() -> list[ContextItem]:
    """Tier-A items for one live-shaped turn: NPC self-state plus its surroundings."""
    return [
        ContextItem(key="character:mira_innkeeper", text=_sized("c", 145), tier="tierA", priority=PRIORITY_CHARACTER, pinned=True),
        ContextItem(key="session", text=serialize_json([]), tier="tierA", priority=PRIORITY_SESSION, pinned=True),
        ContextItem(key="location:loc_tavern", text=_sized("l", 2188), tier="tierA", priority=PRIORITY_LOCATION),
        ContextItem(key="nearby_npcs", text=_sized("n", 91), tier="tierA", priority=PRIORITY_NEARBY),
        ContextItem(key="memories", text=serialize_json(_seeded_memory()), tier="tierA", priority=PRIORITY_MEMORIES),
        ContextItem(key="event:0:mira_innkeeper", text=_sized("e", 17), tier="tierA", priority=PRIORITY_EVENT),
        ContextItem(key="beliefs", text=serialize_json(_seeded_belief()), tier="tierA", priority=PRIORITY_BELIEFS),
        ContextItem(key="goals", text=serialize_json([{"id": "goal_mira_innkeeper_0", "description": "Keep the Flagon neutral.", "urgency": 60}]), tier="tierA", priority=PRIORITY_GOALS),
    ]


def _tier0_items() -> list[ContextItem]:
    """Pinned tier-0 items at their live token sizes."""
    return [
        ContextItem(key="world", text=_sized("w", 60), tier="tier0", priority=100, pinned=True),
        ContextItem(key="emotion", text=_sized("m", 16), tier="tier0", priority=95, pinned=True),
    ]


def _assemble() -> dict[str, Any]:
    """Run rank -> merge -> budget -> serialize and return the parsed prompt skeleton."""
    llm_config = _llm_config()
    tier_a = rank_tier_items(items=_tier_a_items(), llm_config=llm_config, vector_scores={})
    merged: MergedContext = merge_context(tier0=_tier0_items(), tier_a=tier_a, tier_b=[], tier_c=[])
    _final_context, serialized = fill_to_budget(
        context=merged, llm_config=llm_config, prompt_token_budget=PRODUCTION_PROMPT_BUDGET,
    )
    return dict(json.loads(serialized))


class TestInnerLifeSurvivesToSerializedPrompt:
    """ISSUE-163: the NPC's own state must outrank its surroundings for tier-A budget."""

    def test_seeded_belief_reaches_npc_beliefs_slot(self) -> None:
        """A belief the graph holds must appear in npc.beliefs, not be ranked out.

        Fails before the proximity fix: `beliefs` scores proximity 0.0 — the same as a
        node at the horizon — so `nearby_npcs` and `event:0` take the 131 tokens the
        281-token tier-A cap leaves after the pinned character node.
        """
        beliefs = _assemble()["npc"]["beliefs"]
        assert [b["id"] for b in beliefs] == [SEEDED_BELIEF_ID]

    def test_zero_vividness_memory_reaches_npc_memories_slot(self) -> None:
        """A vividness=0 memory must reach npc.memories — vividness is not a filter."""
        memories = _assemble()["npc"]["memories"]
        assert [m["id"] for m in memories] == [SEEDED_MEMORY_ID]
        assert memories[0]["vividness"] == 0

    def test_npc_self_state_outranks_surroundings(self) -> None:
        """Beliefs, goals and memories must rank above nearby_npcs, which is 1 hop away."""
        ranked = rank_tier_items(items=_tier_a_items(), llm_config=_llm_config(), vector_scores={})
        order = [item.key for item in ranked]
        for self_state_key in ("memories", "beliefs", "goals"):
            assert order.index(self_state_key) < order.index("nearby_npcs"), order
