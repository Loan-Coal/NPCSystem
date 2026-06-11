"""
test_context_metrics_observability_v14.py - Tests context pipeline metrics emission.

Does NOT: execute real Neo4j queries.

Dependencies injected: Monkeypatched readers and embedding index.
"""

import pytest

from npc_engine.config import Settings
from npc_engine.retrieval.context_builder import build_serialized_context
from npc_engine.retrieval.context_merger import ContextItem
from npc_engine.schema.context_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens
from npc_engine.utils.metrics import get_counter_value, reset_metrics_registry
from npc_engine.world.world_state import WorldState


class FakeEmbeddingIndex:
    """Simple fake embedding index for context metric tests."""

    async def search(self, query: str, top_k: int, filter_ids=None):
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
            recency=0.30,
            severity=0.2,
            proximity=0.2,
            relation=0.2,
            quest=0.1,
        ),
    )


def setup_function() -> None:
    reset_metrics_registry()


@pytest.mark.asyncio
async def test_context_builder_emits_tier_item_and_token_metrics(monkeypatch) -> None:
    """Context build should emit selected-item and token counters for tiers."""

    async def fake_world_reader(session, world_id: str = "world"):
        return WorldState(epoch="age_of_peace")

    async def fake_character_reader(session, npc_id):
        return {"character": {"id": npc_id, "current_mood": "neutral"}, "relations": []}

    async def fake_location_id(session, npc_id):
        return ""

    async def fake_location_context(session, location_id):
        return {}

    async def fake_events(session, npc_id, limit):
        return []

    async def fake_reputation(session, npc_id, player_id, threshold):
        return []

    async def fake_known_event_ids(session, npc_id):
        return set()

    def fake_assemble(*, npc_id, character_bundle, events, location_id, location_context, group_memberships=None, believed_rumors=None, traits=None, active_pledges=None):
        return [ContextItem(key=f"character:{npc_id}", text='{"id":"npc_1"}', tier="tierA", priority=80)]

    async def fake_memories(session, *, character_id, k):
        return []

    async def fake_beliefs(session, *, character_id, k):
        return []

    async def fake_goals(session, *, character_id, k, status_filter="active"):
        return []

    async def fake_items(session, *, character_id, k=10):
        return []

    async def fake_secrets(session, *, character_id, k):
        return []

    async def fake_obligations(session, *, character_id, k):
        return []

    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_world_state", fake_world_reader)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_character_with_relations", fake_character_reader)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_known_event_ids_for_npc", fake_known_event_ids)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_npc_location_id", fake_location_id)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_location_context", fake_location_context)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_events_for_npc", fake_events)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_reputation_context_for_npc", fake_reputation)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.assemble_tier_a_context", fake_assemble)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_memories_for_character", fake_memories)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_beliefs_for_character", fake_beliefs)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_goals_for_character", fake_goals)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_items_for_character", fake_items)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_secrets_for_character", fake_secrets)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_debts_for_character", fake_obligations)

    async def fake_group_memberships(session, *, character_id, include_dissolved=False):
        return []

    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_groups_for_character_svc", fake_group_memberships)

    async def fake_believed_rumors(session, *, character_id, min_confidence=0):
        return []

    async def fake_traits(session, character_id):
        return []

    async def fake_pledges(session, character_id, active_only=True):
        return []

    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_rumors_for_character_svc", fake_believed_rumors)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_traits_svc", fake_traits)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_pledges_for_character_svc", fake_pledges)

    async def fake_trust_scores(session, *, npc_id, event_ids):
        return {}

    async def fake_second_hop(session, *, npc_id, trust_threshold=50, limit=5):
        return []

    async def fake_active_quest(session, *, player_id):
        return None

    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_trust_scores_for_events", fake_trust_scores)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_second_hop_events", fake_second_hop)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_active_quest_for_player", fake_active_quest)

    async def fake_needs(session, character_id):
        return []

    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_needs_for_character", fake_needs)

    async def fake_player_memories(session, *, npc_id, player_id, k=5):
        return []

    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_player_memories_for_npc", fake_player_memories)

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
