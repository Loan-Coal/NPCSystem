"""
test_context_builder.py - Unit tests for end-to-end serialized context assembly.

Does NOT: execute real Neo4j queries.

Dependencies injected: Monkeypatched retrieval and world readers.
"""

import json

import pytest

from npc_engine.config import Settings
from npc_engine.retrieval.context_builder import _enforce_final_serialized_budget, _estimate_tokens, build_serialized_context
from npc_engine.retrieval.context_merger import ContextItem, MergedContext
from npc_engine.retrieval.context_serializer import serialize_context
from npc_engine.retrieval.vector_store_protocol import VectorSearchResult
from npc_engine.schema.context_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens
from npc_engine.world.world_state import WorldState


class FakeEmbeddingIndex:
    """Simple fake embedding index for builder tests."""

    def __init__(self, rows: list[VectorSearchResult]):
        self._rows = rows

    async def search(self, query: str, top_k: int, filter_ids=None) -> list[VectorSearchResult]:
        results = self._rows[:top_k]
        if filter_ids is not None:
            results = [r for r in results if r["id"] in filter_ids]
        return results


def _llm_config() -> LLMConfig:
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=4000, tier_b=3000, tier_c=2000),
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


def _patch_graph_calls(monkeypatch, tier_a_items=None) -> None:
    """Patch all graph calls used by build_serialized_context."""

    async def fake_world_reader(session, world_id: str = "world"):
        return WorldState(epoch="age_of_peace")

    async def fake_character_reader(session, npc_id):
        return {"character": {"id": npc_id, "current_mood": "anxious"}, "relations": []}

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

    async def fake_group_memberships(session, *, character_id, include_dissolved=False):
        return []

    _items = tier_a_items or []

    def fake_assemble(*, npc_id, character_bundle, events, location_id, location_context, group_memberships=None, believed_rumors=None, traits=None, active_pledges=None):
        return _items

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


@pytest.mark.asyncio
async def test_builder_outputs_fixed_schema_with_emotion(monkeypatch) -> None:
    _patch_graph_calls(
        monkeypatch,
        tier_a_items=[
            ContextItem(
                key="character:npc_1",
                text='{"id":"npc_1","name":"Aldric"}',
                tier="tierA",
                priority=100,
            )
        ],
    )

    settings = Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
        PROMPT_TOKEN_BUDGET=800,
    )

    serialized = await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=settings,
        llm_config=_llm_config(),
        embedding_index=FakeEmbeddingIndex(rows=[]),
        npc_id="npc_1",
        player_message="hello",
        session_turns=["player: hi"],
    )
    payload = json.loads(serialized)
    assert payload["npc"]["emotion"]["current_mood"] == "anxious"
    assert "recent_session_turns" in payload


@pytest.mark.asyncio
async def test_builder_enforces_final_serialized_budget(monkeypatch) -> None:
    _patch_graph_calls(
        monkeypatch,
        tier_a_items=[
            ContextItem(key="event:0", text='{"summary":"x"}', tier="tierA", priority=10),
            ContextItem(key="event:1", text='{"summary":"y"}', tier="tierA", priority=9),
        ],
    )

    settings = Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
        PROMPT_TOKEN_BUDGET=200,
    )

    serialized = await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=settings,
        llm_config=_llm_config(),
        embedding_index=FakeEmbeddingIndex(rows=[{"id": "r1", "score": 1.0, "payload": {"summary": "z" * 300}}]),
        npc_id="npc_1",
        player_message="hello",
        session_turns=["player: hi"],
    )

    estimated_tokens = max(1, (len(serialized) + 3) // 4)
    assert estimated_tokens <= settings.PROMPT_TOKEN_BUDGET


@pytest.mark.asyncio
async def test_builder_passes_known_event_ids_as_filter_to_embedding_index(monkeypatch) -> None:
    """When the NPC has known event IDs, the embedding index receives them as filter_ids."""

    captured: dict = {}

    class CapturingEmbeddingIndex:
        async def search(self, query: str, top_k: int, filter_ids=None) -> list[VectorSearchResult]:
            captured["filter_ids"] = filter_ids
            return []

    async def fake_known_event_ids_non_empty(session, npc_id):
        return {"evt_1", "evt_2"}

    _patch_graph_calls(monkeypatch)
    monkeypatch.setattr(
        "npc_engine.retrieval.context_builder.get_known_event_ids_for_npc",
        fake_known_event_ids_non_empty,
    )

    settings = Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
        PROMPT_TOKEN_BUDGET=2500,
    )

    await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=settings,
        llm_config=_llm_config(),
        embedding_index=CapturingEmbeddingIndex(),
        npc_id="npc_1",
        player_message="hello",
        session_turns=[],
    )

    assert captured.get("filter_ids") == {"evt_1", "evt_2"}


@pytest.mark.asyncio
async def test_builder_passes_no_filter_when_known_event_ids_empty(monkeypatch) -> None:
    """When the NPC has no known event IDs, filter_ids is None (no restriction)."""

    captured: dict = {}

    class CapturingEmbeddingIndex:
        async def search(self, query: str, top_k: int, filter_ids=None) -> list[VectorSearchResult]:
            captured["filter_ids"] = filter_ids
            return []

    _patch_graph_calls(monkeypatch)

    settings = Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
        PROMPT_TOKEN_BUDGET=2500,
    )

    await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=settings,
        llm_config=_llm_config(),
        embedding_index=CapturingEmbeddingIndex(),
        npc_id="npc_1",
        player_message="hello",
        session_turns=[],
    )

    assert captured.get("filter_ids") is None


def test_final_serialized_budget_drops_tier_c_before_tier_b_when_over_budget() -> None:
    merged = MergedContext(
        items=[
            ContextItem(key="world", text='{"epoch":"age_of_peace"}', tier="tier0", priority=100),
            ContextItem(key="session", text='["player: hi"]', tier="tierA", priority=99),
            ContextItem(key="rag:b", text=("B" * 200), tier="tierB", priority=30),
            ContextItem(key="rag:c", text=("C" * 200), tier="tierC", priority=30),
        ]
    )
    one_drop_context = merged.model_copy(
        update={
            "items": [item for item in merged.items if item.key != "rag:c"],
        }
    )
    one_drop_budget = _estimate_tokens(serialize_context(context=one_drop_context))

    serialized = _enforce_final_serialized_budget(context=merged, budget=one_drop_budget)

    assert "BBBB" in serialized
    assert "CCCC" not in serialized
