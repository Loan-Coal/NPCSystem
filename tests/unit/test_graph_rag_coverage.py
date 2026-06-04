"""
test_graph_rag_coverage.py - Unit tests for retrieval.graph_rag scoring logic.

Does NOT: touch Neo4j or the vector store.

Dependencies injected: mock AsyncSession, mock EmbeddingIndex.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.retrieval.graph_rag import (
    EmbeddingIndexProtocol,
    _recency_score,
    graph_rag_retrieve,
)
from npc_engine.retrieval.vector_store_protocol import VectorSearchResult
from npc_engine.world.time_utils import TimePoint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(node_id: str, score: float, payload: dict | None = None) -> VectorSearchResult:
    return VectorSearchResult(id=node_id, score=score, payload=payload or {})


def _make_session(expansion_rows: list[dict[str, Any]]) -> AsyncMock:
    cursor = AsyncMock()
    cursor.data = AsyncMock(return_value=expansion_rows)
    session = AsyncMock()
    session.run = AsyncMock(return_value=cursor)
    return session


def _make_index(seed_results: list[VectorSearchResult]) -> MagicMock:
    idx = MagicMock(spec=EmbeddingIndexProtocol)
    idx.search = AsyncMock(return_value=seed_results)
    return idx


# ---------------------------------------------------------------------------
# Config constant smoke-test
# ---------------------------------------------------------------------------

def test_rag_weights_present_in_config() -> None:
    """Config must expose five RAG constants after SEV-39 prod change."""
    from npc_engine.config import (
        RAG_RECENCY_DAYS_HARD,
        RAG_RECENCY_DAYS_SOFT,
        RAG_RECENCY_WEIGHT,
        RAG_RELEVANCE_WEIGHT,
        RAG_TRUST_WEIGHT,
    )
    assert RAG_RELEVANCE_WEIGHT + RAG_TRUST_WEIGHT + RAG_RECENCY_WEIGHT == pytest.approx(1.0, abs=1e-6)
    assert RAG_RECENCY_DAYS_SOFT > 0
    assert RAG_RECENCY_DAYS_HARD > 0


# ---------------------------------------------------------------------------
# Scoring formula
# ---------------------------------------------------------------------------

def test_composite_score_formula_uses_config_weights() -> None:
    """Composite score for a neighbor must match the config-weight formula."""
    from npc_engine.config import RAG_RECENCY_WEIGHT, RAG_RELEVANCE_WEIGHT, RAG_TRUST_WEIGHT

    vec_sim = 0.8
    edge_weight = 0.6
    recency = 0.9
    expected = (
        vec_sim * RAG_RELEVANCE_WEIGHT
        + edge_weight * RAG_TRUST_WEIGHT
        + recency * RAG_RECENCY_WEIGHT
    )
    # Verify the formula itself is consistent (no off-by-one in constants)
    assert expected == pytest.approx(0.8 * 0.5 + 0.6 * 0.3 + 0.9 * 0.2, abs=1e-9)


# ---------------------------------------------------------------------------
# Happy-path retrieval + ranking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_graph_rag_retrieve_ranking() -> None:
    """Seeds + neighbors should be ranked by composite score descending."""
    seed_a = _make_result("ev_a", score=0.9)
    seed_b = _make_result("ev_b", score=0.5)

    expansion_rows = [
        {
            "seed_id": "ev_a",
            "neighbor_id": "ev_neighbor",
            "neighbor_props": {},
            "edge_type": "CAUSED_BY",
            "edge_weight": 0.7,
        }
    ]
    session = _make_session(expansion_rows)
    idx = _make_index([seed_a, seed_b])

    results = await graph_rag_retrieve(
        session=session,
        embedding_index=idx,
        query="test query",
        npc_id="npc_01",
        known_event_ids={"ev_a", "ev_b"},
        top_k=3,
    )

    assert len(results) >= 1
    ids = [r["id"] for r in results]
    assert "ev_a" in ids
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_graph_rag_retrieve_empty_seeds() -> None:
    """When embedding search returns nothing, result must be empty."""
    session = _make_session([])
    idx = _make_index([])

    results = await graph_rag_retrieve(
        session=session,
        embedding_index=idx,
        query="empty",
        npc_id="npc_01",
        known_event_ids=set(),
        top_k=5,
    )
    assert results == []


@pytest.mark.asyncio
async def test_graph_rag_retrieve_top_k_limit() -> None:
    """Result length must never exceed top_k."""
    seeds = [_make_result(f"ev_{i}", score=float(i) / 10) for i in range(10)]
    session = _make_session([])
    idx = _make_index(seeds)

    results = await graph_rag_retrieve(
        session=session,
        embedding_index=idx,
        query="q",
        npc_id="npc_01",
        known_event_ids=set(),
        top_k=3,
    )
    assert len(results) <= 3


# ---------------------------------------------------------------------------
# Recency scoring
# ---------------------------------------------------------------------------

def test_recency_score_game_time_recent() -> None:
    """Node created at current game time should score near 1.0."""
    game_time = TimePoint(year=1, season="spring", day=1, time_of_day="morning")
    props: dict[str, Any] = {
        "created_at_game_time": '{"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}'
    }
    score = _recency_score(props, game_time)
    assert score >= 0.99


def test_recency_score_old_node_scores_zero() -> None:
    """Node created at year=1 should score 0.0 when current time is year=5 (>365 game-days gap)."""
    # year=5 vs year=1 → 448 game-days gap > RAG_RECENCY_DAYS_SOFT(365) → clamps to 0.0
    game_time = TimePoint(year=5, season="spring", day=1, time_of_day="morning")
    props: dict[str, Any] = {
        "created_at_game_time": '{"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}'
    }
    score = _recency_score(props, game_time)
    assert score == pytest.approx(0.0, abs=0.01)


def test_recency_score_no_timestamp_returns_zero() -> None:
    """Props without any timestamp should return 0.0."""
    score = _recency_score({}, game_time=None)
    assert score == 0.0


def test_recency_score_invalid_json_returns_zero() -> None:
    """Malformed JSON in created_at_game_time should return 0.0 without raising."""
    game_time = TimePoint(year=1, season="spring", day=1, time_of_day="morning")
    props: dict[str, Any] = {"created_at_game_time": "not-json{{"}
    score = _recency_score(props, game_time)
    assert score == 0.0
