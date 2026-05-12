"""
test_context_metrics_observability_v14.py - Tests context pipeline metrics emission.

Does NOT: execute real Neo4j queries.

Dependencies injected: Monkeypatched readers and embedding index.
"""

import pytest

from npc_engine.config import Settings
from npc_engine.retrieval.context_builder import build_serialized_context
from npc_engine.retrieval.context_merger import ContextItem
from npc_engine.schema.llm_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens
from npc_engine.utils.metrics import get_counter_value, reset_metrics_registry
from npc_engine.world.world_state import WorldState


class FakeEmbeddingIndex:
    """Simple fake embedding index for context metric tests."""

    async def search(self, query: str, top_k: int):
        return [{"id": "r1", "score": 0.9, "payload": {"summary": "rumor", "severity": 75}}]


def _llm_config() -> LLMConfig:
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=500, tier_b=300, tier_c=200),
        session_turns_budget_tokens=200,
        compression_trigger_ratio=0.9,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.25,
            severity=0.2,
            proximity=0.2,
            relation=0.2,
            quest=0.1,
            explicit=0.05,
        ),
    )


def setup_function() -> None:
    reset_metrics_registry()


@pytest.mark.asyncio
async def test_context_builder_emits_tier_item_and_token_metrics(monkeypatch) -> None:
    """Context build should emit selected-item and token counters for tiers."""

    async def fake_world_reader(session):
        return WorldState(epoch="age_of_peace")

    async def fake_character_reader(session, npc_id):
        return {"character": {"id": npc_id, "current_mood": "neutral"}, "relations": []}

    async def fake_tier_a_reader(session, npc_id, event_limit):
        return [ContextItem(key=f"character:{npc_id}", text='{"id":"npc_1"}', tier="tierA", priority=80)]

    async def fake_memories(session, *, character_id, k):
        return []

    async def fake_beliefs(session, *, character_id, k):
        return []

    async def fake_goals(session, *, character_id, k, status_filter="active"):
        return []

    async def fake_items(session, *, character_id):
        return []

    async def fake_secrets(session, *, character_id, k):
        return []

    async def fake_obligations(session, *, character_id, k):
        return []

    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_world_state", fake_world_reader)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_character_with_relations", fake_character_reader)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.retrieve_tier_a_context", fake_tier_a_reader)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_memories_for_character", fake_memories)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_beliefs_for_character", fake_beliefs)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_goals_for_character", fake_goals)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_items_for_character", fake_items)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_secrets_for_character", fake_secrets)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_debts_for_character", fake_obligations)

    settings = Settings(API_KEY_SECRET="npc_dev_secret_2026_alpha")

    await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=settings,
        llm_config=_llm_config(),
        embedding_index=FakeEmbeddingIndex(),
        npc_id="npc_1",
        player_message="hello",
        session_turns=["player: hi"],
    )

    tier_a_items = get_counter_value("context_items_selected_total", labels={"tier": "tiera"})
    tier_b_tokens = get_counter_value("context_tier_tokens", labels={"tier": "tierb"})

    assert tier_a_items >= 1.0
    assert tier_b_tokens > 0.0
