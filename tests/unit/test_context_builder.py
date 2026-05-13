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
from npc_engine.schema.llm_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens
from npc_engine.world.world_state import WorldState


class FakeEmbeddingIndex:
    """Simple fake embedding index for builder tests."""

    def __init__(self, rows: list[VectorSearchResult]):
        self._rows = rows

    async def search(self, query: str, top_k: int) -> list[VectorSearchResult]:
        return self._rows[:top_k]


def _llm_config() -> LLMConfig:
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=4000, tier_b=3000, tier_c=2000),
        session_turns_budget_tokens=1200,
        compression_trigger_ratio=0.85,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.25,
            severity=0.20,
            proximity=0.20,
            relation=0.20,
            quest=0.10,
            explicit=0.05,
        ),
    )


@pytest.mark.asyncio
async def test_builder_outputs_fixed_schema_with_emotion(monkeypatch) -> None:
    async def fake_world_reader(session):
        return WorldState(epoch="age_of_peace")

    async def fake_character_reader(session, npc_id):
        return {"character": {"id": npc_id, "current_mood": "anxious"}, "relations": []}

    async def fake_tier_a(session, npc_id, event_limit):
        return [
            ContextItem(
                key=f"character:{npc_id}",
                text='{"id":"npc_1","name":"Aldric"}',
                tier="tierA",
                priority=100,
            )
        ]

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
    monkeypatch.setattr("npc_engine.retrieval.context_builder.retrieve_tier_a_context", fake_tier_a)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_memories_for_character", fake_memories)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_beliefs_for_character", fake_beliefs)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_goals_for_character", fake_goals)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_items_for_character", fake_items)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_secrets_for_character", fake_secrets)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_debts_for_character", fake_obligations)

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
    async def fake_world_reader(session):
        return WorldState(epoch="age_of_peace")

    async def fake_character_reader(session, npc_id):
        return {"character": {"id": npc_id, "current_mood": "neutral"}, "relations": []}

    async def fake_tier_a(session, npc_id, event_limit):
        return [
            ContextItem(key="event:0", text='{"summary":"x"}', tier="tierA", priority=10),
            ContextItem(key="event:1", text='{"summary":"y"}', tier="tierA", priority=9),
        ]

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
    monkeypatch.setattr("npc_engine.retrieval.context_builder.retrieve_tier_a_context", fake_tier_a)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_memories_for_character", fake_memories)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_beliefs_for_character", fake_beliefs)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_goals_for_character", fake_goals)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_items_for_character", fake_items)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_secrets_for_character", fake_secrets)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_debts_for_character", fake_obligations)

    settings = Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
        PROMPT_TOKEN_BUDGET=120,
    )

    serialized = await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=settings,
        llm_config=_llm_config(),
        embedding_index=FakeEmbeddingIndex(rows=[{"id": "r1", "score": 1.0, "payload": {"summary": "z"}}]),
        npc_id="npc_1",
        player_message="hello",
        session_turns=["player: hi"],
    )

    estimated_tokens = max(1, (len(serialized) + 3) // 4)
    assert estimated_tokens <= settings.PROMPT_TOKEN_BUDGET


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
