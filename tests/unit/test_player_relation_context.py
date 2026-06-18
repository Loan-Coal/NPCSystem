"""
test_player_relation_context.py - Unit tests for player-scoped relation edge in context assembly.

Tests that build_serialized_context includes the RELATES_TO edge properties as a
named top-level `player_relation` key in Tier-A when player_id is provided and the
edge exists, and excludes it otherwise.

Does NOT: execute real Neo4j queries.
"""

from __future__ import annotations

import json

import pytest

from npc_engine.config import Settings
from npc_engine.retrieval.context_builder import build_serialized_context
from npc_engine.schema.context_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens
from npc_engine.world.world_state import WorldState


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

FAKE_EDGE: dict = {"trust": 60, "fear": 5, "affection": 40, "interaction_count": 3}


def _settings() -> Settings:
    return Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
        PROMPT_TOKEN_BUDGET=2500,
    )


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


def _patch_graph_calls(monkeypatch) -> None:
    """Patch all graph calls used by build_serialized_context with minimal fakes."""

    async def fake_world_reader(session):
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

    async def fake_believed_rumors(session, *, character_id, min_confidence=0):
        return []

    async def fake_traits(session, character_id):
        return []

    async def fake_pledges(session, character_id, active_only=True):
        return []

    async def fake_trust_scores(session, *, npc_id, event_ids):
        return {}

    async def fake_second_hop(session, *, npc_id, trust_threshold=50, limit=5):
        return []

    async def fake_active_quest(session, *, player_id):
        return None

    def fake_assemble(*, npc_id, character_bundle, events, location_id, location_context, group_memberships=None, believed_rumors=None, traits=None, active_pledges=None):
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
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_groups_for_character_svc", fake_group_memberships)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_rumors_for_character_svc", fake_believed_rumors)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_traits_svc", fake_traits)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_pledges_for_character_svc", fake_pledges)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_trust_scores_for_events", fake_trust_scores)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_second_hop_events", fake_second_hop)
    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_active_quest_for_player", fake_active_quest)

    async def fake_needs(session, character_id):
        return []

    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_needs_for_character", fake_needs)

    async def fake_player_memories(session, *, npc_id, player_id, k=5):
        return []

    monkeypatch.setattr("npc_engine.retrieval.context_builder.get_player_memories_for_npc", fake_player_memories)


class FakeEmbeddingIndex:
    """Minimal fake embedding index — returns empty results."""

    async def search(self, query: str, top_k: int, filter_ids=None):
        """Return empty search results."""
        return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_player_relation_included_when_player_id_provided(monkeypatch) -> None:
    """player_id provided + edge found → serialized JSON contains 'player_relation' key."""
    _patch_graph_calls(monkeypatch)

    async def fake_npc_player_edge(session, *, npc_id, player_id):
        return FAKE_EDGE

    monkeypatch.setattr(
        "npc_engine.retrieval.context_builder.get_npc_player_edge",
        fake_npc_player_edge,
    )

    serialized = await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=_settings(),
        llm_config=_llm_config(),
        embedding_index=FakeEmbeddingIndex(),
        npc_id="mira_innkeeper",
        player_message="hello",
        session_turns=[],
        player_id="player_demo",
    )

    payload = json.loads(serialized)
    # context_serializer maps the 'relation:player' ContextItem key to top-level 'player_relation'
    assert payload.get("player_relation"), (
        "Expected non-empty top-level 'player_relation' in payload when player_id is provided and edge exists"
    )


@pytest.mark.asyncio
async def test_player_relation_excluded_when_no_player_id(monkeypatch) -> None:
    """player_id=None → 'player_relation' key must NOT appear in context."""
    _patch_graph_calls(monkeypatch)

    # get_npc_player_edge should never be called, but patch it to a sentinel to detect misuse
    called: list[bool] = []

    async def fake_npc_player_edge(session, *, npc_id, player_id):
        called.append(True)
        return FAKE_EDGE

    monkeypatch.setattr(
        "npc_engine.retrieval.context_builder.get_npc_player_edge",
        fake_npc_player_edge,
    )

    serialized = await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=_settings(),
        llm_config=_llm_config(),
        embedding_index=FakeEmbeddingIndex(),
        npc_id="mira_innkeeper",
        player_message="hello",
        session_turns=[],
        player_id=None,
    )

    assert not called, "get_npc_player_edge must not be called when player_id is None"
    payload = json.loads(serialized)
    # When player_id is None the serializer still emits the key, but the value must be empty dict
    assert payload.get("player_relation") == {}, (
        "Expected empty 'player_relation' when player_id is None (no edge queried)"
    )


@pytest.mark.asyncio
async def test_player_relation_excluded_when_edge_missing(monkeypatch) -> None:
    """player_id set but get_npc_player_edge returns None → key absent from context."""
    _patch_graph_calls(monkeypatch)

    async def fake_npc_player_edge(session, *, npc_id, player_id):
        return None

    monkeypatch.setattr(
        "npc_engine.retrieval.context_builder.get_npc_player_edge",
        fake_npc_player_edge,
    )

    serialized = await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=_settings(),
        llm_config=_llm_config(),
        embedding_index=FakeEmbeddingIndex(),
        npc_id="mira_innkeeper",
        player_message="hello",
        session_turns=[],
        player_id="player_demo",
    )

    payload = json.loads(serialized)
    # When edge is None the serializer still emits the key, but the value must be empty dict
    assert payload.get("player_relation") == {}, (
        "Expected empty 'player_relation' when edge is None"
    )


@pytest.mark.asyncio
async def test_player_relation_not_pinned_in_tier_a(monkeypatch) -> None:
    """The player_relation ContextItem must have pinned=False (non-pinned, budget-droppable)."""
    _patch_graph_calls(monkeypatch)

    async def fake_npc_player_edge(session, *, npc_id, player_id):
        return FAKE_EDGE

    monkeypatch.setattr(
        "npc_engine.retrieval.context_builder.get_npc_player_edge",
        fake_npc_player_edge,
    )

    # Capture the tier_a_raw list before ranking by monkeypatching rank_tier_items.
    captured_items: list = []
    original_rank = __import__(
        "npc_engine.retrieval.context_scoring", fromlist=["rank_tier_items"]
    ).rank_tier_items

    def capturing_rank(*, items, **kwargs):
        captured_items.extend(items)
        return original_rank(items=items, **kwargs)

    monkeypatch.setattr("npc_engine.retrieval.context_builder.rank_tier_items", capturing_rank)

    await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=_settings(),
        llm_config=_llm_config(),
        embedding_index=FakeEmbeddingIndex(),
        npc_id="mira_innkeeper",
        player_message="hello",
        session_turns=[],
        player_id="player_demo",
    )

    # ContextItem key is 'relation:player' (maps to top-level 'player_relation' via serializer)
    relation_items = [item for item in captured_items if item.key == "relation:player"]
    assert relation_items, "Expected a ContextItem with key='relation:player' in tier_a_raw"
    item = relation_items[0]
    # Non-pinned = lives in tierA (not tier0), so it can be budget-dropped.
    assert item.tier == "tierA", (
        f"relation:player ContextItem must be in tierA (budget-droppable); got tier={item.tier}"
    )
    assert item.priority == 88, (
        f"relation:player ContextItem must have priority=88; got priority={item.priority}"
    )
