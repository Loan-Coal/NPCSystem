"""
graph_rag.py - GraphRAG unified Tier B/C retrieval.
Layer: retrieval
Purpose: (auto-detected — review)

Replaces the raw vector-score ranking for Tier B/C with a graph-aware scoring
that combines vector similarity, trust-weighted 1-hop graph expansion, and
recency. Enabled via settings.GRAPH_RAG_ENABLED.

Algorithm:
  1. Vector-search for top-K seed node IDs (filtered to NPC's KNOWS_ABOUT set).
  2. Expand each seed 1 hop along semantically meaningful edges via Neo4j.
  3. Score each candidate:
       score = (vector_sim * _RAG_RELEVANCE_WEIGHT) + (edge_weight * _RAG_TRUST_WEIGHT) + (recency * _RAG_RECENCY_WEIGHT)
  4. De-duplicate by node ID, keep highest score per node.
  5. Return ranked list of VectorSearchResult-compatible dicts.

Does NOT: write to the graph or call LLM adapters.
Dependencies injected: EmbeddingIndexProtocol, AsyncSession.
Used by: retrieval.context_builder (when GRAPH_RAG_ENABLED=True).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from neo4j import AsyncSession

from npc_engine.retrieval.vector_store_protocol import VectorSearchResult
from npc_engine.world.time_utils import TimePoint, total_days


# GraphRAG composite-score weights. Canonical values live in npc_engine.config
# (RAG_RELEVANCE_WEIGHT, RAG_TRUST_WEIGHT, RAG_RECENCY_WEIGHT, RAG_RECENCY_DAYS_SOFT,
#  RAG_RECENCY_DAYS_HARD). Mirrored here as typed module-level constants so this
# module has no runtime dependency on config and mypy can type-check correctly.
_RAG_RELEVANCE_WEIGHT: float = 0.5   # vector-similarity component weight
_RAG_TRUST_WEIGHT: float = 0.3       # graph edge-weight component weight
_RAG_RECENCY_WEIGHT: float = 0.2     # temporal recency component weight
_RAG_RECENCY_DAYS_SOFT: float = 365.0  # game-time: full decay over N game-days
_RAG_RECENCY_DAYS_HARD: float = 72.0   # wall-clock: full decay over N real hours


# Edge types to traverse during 1-hop expansion. These represent relationships
# where the neighbor provides semantically related context to the seed node.
_EXPANSION_EDGE_TYPES = frozenset({
    "KNOWS_ABOUT",
    "CAUSED_BY",
    "WITNESSED",
    "BELIEVED_RUMOR",
    "REMEMBERS",
    "PART_OF_CHAPTER",
})

_CYPHER_EXPAND_SEEDS = """
UNWIND $seed_ids AS seed_id
MATCH (seed) WHERE seed.id = seed_id
MATCH (seed)-[r]-(neighbor)
WHERE type(r) IN $edge_types
  AND neighbor.id IS NOT NULL
RETURN
    seed_id,
    neighbor.id AS neighbor_id,
    properties(neighbor) AS neighbor_props,
    type(r) AS edge_type,
    CASE
        WHEN r.trust IS NOT NULL THEN toFloat(r.trust) / 100.0
        WHEN r.confidence IS NOT NULL THEN toFloat(r.confidence) / 100.0
        ELSE 0.5
    END AS edge_weight
"""


class EmbeddingIndexProtocol(Protocol):
    async def search(
        self,
        query: str,
        top_k: int,
        filter_ids: set[str] | None = None,
    ) -> list[VectorSearchResult]: ...


def _recency_score(props: dict[str, Any], game_time: TimePoint | None) -> float:
    """Compute recency score for a node's properties."""
    raw_game_time = props.get("created_at_game_time") or props.get("occurred_at_game_time")
    if raw_game_time is not None and game_time is not None:
        try:
            import json as _json
            gt = _json.loads(raw_game_time) if isinstance(raw_game_time, str) else raw_game_time
            node_tp = TimePoint(
                year=int(gt.get("year", 0)),
                season=str(gt.get("season", "spring")),
                day=int(gt.get("day", 1)),
                time_of_day=str(gt.get("time_of_day", "morning")),
            )
            age_days = max(0, total_days(game_time) - total_days(node_tp))
            return max(0.0, min(1.0, 1.0 - min(age_days / _RAG_RECENCY_DAYS_SOFT, 1.0)))
        except (KeyError, TypeError, ValueError):
            return 0.0
    for field in ("occurred_at", "updated_at", "last_graph_updated_at", "created_at"):
        raw = props.get(field)
        if not isinstance(raw, str):
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age_hours = max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0)
            return max(0.0, min(1.0, 1.0 - min(age_hours / _RAG_RECENCY_DAYS_HARD, 1.0)))
        except ValueError:
            continue
    return 0.0


async def graph_rag_retrieve(
    session: AsyncSession,
    embedding_index: EmbeddingIndexProtocol,
    query: str,
    npc_id: str,
    known_event_ids: set[str],
    top_k: int,
    game_time: TimePoint | None = None,
) -> list[VectorSearchResult]:
    """GraphRAG unified retrieval: vector seeds → graph expansion → composite scoring.

    Args:
        session: Active Neo4j async session.
        embedding_index: Vector search backend.
        query: Expanded query string for vector search.
        npc_id: ID of the NPC; used to enforce knowledge boundary via known_event_ids.
        known_event_ids: Set of event IDs the NPC has KNOWS_ABOUT edges for.
        top_k: Number of results to return.
        game_time: Current game time for recency scoring (optional).

    Returns:
        Ranked list of VectorSearchResult dicts, length ≤ top_k.
    """
    rag_filter = known_event_ids if known_event_ids else None
    seed_results: list[VectorSearchResult] = await embedding_index.search(
        query=query,
        top_k=top_k * 2,  # fetch extra seeds to allow for graph expansion filtering
        filter_ids=rag_filter,
    )
    if not seed_results:
        return []

    seed_scores: dict[str, float] = {r["id"]: float(r.get("score", 0.0)) for r in seed_results}
    seed_payloads: dict[str, dict] = {r["id"]: r.get("payload", {}) for r in seed_results}
    seed_ids = list(seed_scores.keys())

    # Expand 1 hop from each seed along semantically relevant edges.
    expansion_result = await session.run(
        _CYPHER_EXPAND_SEEDS,
        seed_ids=seed_ids,
        edge_types=list(_EXPANSION_EDGE_TYPES),
    )
    expansion_records = await expansion_result.data()

    # Accumulate best score per node (seed + neighbors).
    best_scores: dict[str, tuple[float, dict]] = {}

    def _update_best(node_id: str, score: float, props: dict) -> None:
        existing = best_scores.get(node_id)
        if existing is None or score > existing[0]:
            best_scores[node_id] = (score, props)

    for seed_id, vec_sim in seed_scores.items():
        recency = _recency_score(seed_payloads.get(seed_id, {}), game_time)
        composite = vec_sim * _RAG_RELEVANCE_WEIGHT + _RAG_RECENCY_WEIGHT * recency  # seed: no edge_weight component
        _update_best(seed_id, composite, seed_payloads.get(seed_id, {}))

    for row in expansion_records:
        seed_id = row["seed_id"]
        neighbor_id = row["neighbor_id"]
        neighbor_props = dict(row.get("neighbor_props") or {})
        edge_weight = float(row.get("edge_weight") or 0.5)
        vec_sim = seed_scores.get(seed_id, 0.0)
        recency = _recency_score(neighbor_props, game_time)
        composite = vec_sim * _RAG_RELEVANCE_WEIGHT + edge_weight * _RAG_TRUST_WEIGHT + recency * _RAG_RECENCY_WEIGHT
        _update_best(neighbor_id, composite, neighbor_props)

    # Sort by score descending, take top_k, return as VectorSearchResult dicts.
    ranked = sorted(best_scores.items(), key=lambda kv: kv[1][0], reverse=True)
    return [
        VectorSearchResult(id=node_id, score=score, payload=props)
        for node_id, (score, props) in ranked[:top_k]
    ]
