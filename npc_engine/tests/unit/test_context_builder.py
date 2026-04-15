"""
test_context_builder.py - Unit tests for end-to-end serialized context assembly.

Does NOT: execute real Neo4j queries.

Dependencies injected: Monkeypatched retrieval and world readers.
"""

import json

import pytest

from config import Settings
from retrieval.context_builder import build_serialized_context
from retrieval.context_merger import ContextItem
from retrieval.vector_store_protocol import VectorSearchResult
from world.world_state import WorldState


class FakeEmbeddingIndex:
    """Simple fake embedding index for builder tests."""

    def __init__(self, rows: list[VectorSearchResult]):
        self._rows = rows

    async def search(self, query: str, top_k: int) -> list[VectorSearchResult]:
        return self._rows[:top_k]


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

    monkeypatch.setattr("retrieval.context_builder.get_world_state", fake_world_reader)
    monkeypatch.setattr("retrieval.context_builder.get_character_with_relations", fake_character_reader)
    monkeypatch.setattr("retrieval.context_builder.retrieve_tier_a_context", fake_tier_a)

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

    monkeypatch.setattr("retrieval.context_builder.get_world_state", fake_world_reader)
    monkeypatch.setattr("retrieval.context_builder.get_character_with_relations", fake_character_reader)
    monkeypatch.setattr("retrieval.context_builder.retrieve_tier_a_context", fake_tier_a)

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
        embedding_index=FakeEmbeddingIndex(rows=[{"id": "r1", "score": 1.0, "payload": {"summary": "z"}}]),
        npc_id="npc_1",
        player_message="hello",
        session_turns=["player: hi"],
    )

    estimated_tokens = max(1, (len(serialized) + 3) // 4)
    assert estimated_tokens <= settings.PROMPT_TOKEN_BUDGET
