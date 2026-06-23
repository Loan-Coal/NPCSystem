"""
test_context_scoring_phase6.py - Unit tests for Phase 6 additions to context_scoring.

Does NOT: execute I/O or call LLM services.
"""

from __future__ import annotations

import json

import pytest

from npc_engine.retrieval.context import ContextItem
from npc_engine.retrieval.context import rank_tier_items
from npc_engine.schema.context_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens


def _llm_config() -> LLMConfig:
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=4000, tier_b=3000, tier_c=2000),
        session_turns_budget_tokens=1200,
        compression_trigger_ratio=0.85,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.10,
            severity=0.10,
            proximity=0.10,
            relation=0.60,  # make relation dominant for easy assertion
            quest=0.10,
        ),
    )


def _event_item(key: str, priority: int = 50, actor_id: str | None = None) -> ContextItem:
    payload = {"id": key, "summary": "something happened"}
    if actor_id:
        payload["actor_id"] = actor_id
    return ContextItem(key=key, text=json.dumps(payload), tier="tierA", priority=priority)


def _other_item(key: str, priority: int = 50) -> ContextItem:
    return ContextItem(key=key, text=json.dumps({"content": "generic"}), tier="tierA", priority=priority)


# ---------------------------------------------------------------------------
# 6.2 trust_scores blending
# ---------------------------------------------------------------------------


def test_trust_score_boosts_low_priority_event():
    """An event with low priority but high trust should outscore a high-priority event with no trust."""
    low_priority_evt = _event_item("event:0:npc1", priority=10)
    high_priority_evt = _event_item("event:1:npc1", priority=90)

    trust_scores = {"event:0:npc1": 1.0}  # low priority but 100% trust

    ranked = rank_tier_items(
        items=[low_priority_evt, high_priority_evt],
        llm_config=_llm_config(),
        vector_scores={},
        trust_scores=trust_scores,
    )
    # low priority event has trust=1.0: relation = 0.5*0.1 + 0.5*1.0 = 0.55
    # high priority event no trust: relation = priority/100 = 0.9
    # With relation weight=0.6: low=0.33, high=0.54 — high should still win
    assert ranked[0].key == "event:1:npc1"


def test_trust_score_only_applies_to_event_keys():
    """trust_scores should not affect non-event items."""
    non_event = _other_item("beliefs", priority=50)
    ranked = rank_tier_items(
        items=[non_event],
        llm_config=_llm_config(),
        vector_scores={},
        trust_scores={"beliefs": 1.0},  # key doesn't start with "event:"
    )
    assert len(ranked) == 1


def test_trust_scores_none_does_not_break():
    items = [_event_item("event:0:npc1", priority=70)]
    ranked = rank_tier_items(
        items=items,
        llm_config=_llm_config(),
        vector_scores={},
        trust_scores=None,
    )
    assert len(ranked) == 1


# ---------------------------------------------------------------------------
# 6.4 active_quest scoring
# ---------------------------------------------------------------------------


def test_quest_item_key_always_scores_one():
    quest_item = ContextItem(key="active_quest", text=json.dumps({"id": "q1"}), tier="tierA", priority=50)
    ranked = rank_tier_items(
        items=[quest_item],
        llm_config=_llm_config(),
        vector_scores={},
        active_quest=None,
    )
    assert len(ranked) == 1


def test_active_quest_boosts_item_referencing_giver():
    active_quest = {"giver_id": "innkeeper1", "target_id": "merchant1"}
    giver_item = ContextItem(
        key="event:0:npc1",
        text=json.dumps({"actor_id": "innkeeper1", "summary": "innkeeper posted a notice"}),
        tier="tierA",
        priority=40,
    )
    unrelated_item = ContextItem(
        key="event:1:npc1",
        text=json.dumps({"actor_id": "guard5", "summary": "guard changed shift"}),
        tier="tierA",
        priority=40,
    )
    cfg = LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=4000, tier_b=3000, tier_c=2000),
        session_turns_budget_tokens=1200,
        compression_trigger_ratio=0.85,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.0, severity=0.0, proximity=0.0, relation=0.0, quest=1.0
        ),
    )
    ranked = rank_tier_items(
        items=[unrelated_item, giver_item],
        llm_config=cfg,
        vector_scores={},
        active_quest=active_quest,
    )
    assert ranked[0].key == "event:0:npc1"


def test_active_quest_none_falls_back_to_key_check():
    quest_item = ContextItem(
        key="active_quest",
        text=json.dumps({"id": "q1"}),
        tier="tierA",
        priority=50,
    )
    other = ContextItem(key="beliefs", text=json.dumps({"content": "x"}), tier="tierA", priority=50)
    cfg = LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=4000, tier_b=3000, tier_c=2000),
        session_turns_budget_tokens=1200,
        compression_trigger_ratio=0.85,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.0, severity=0.0, proximity=0.0, relation=0.0, quest=1.0
        ),
    )
    ranked = rank_tier_items(
        items=[other, quest_item],
        llm_config=cfg,
        vector_scores={},
        active_quest=None,
    )
    assert ranked[0].key == "active_quest"
