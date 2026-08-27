"""
Module: retrieval_ranking
Layer: evals (eval harness — not part of src/)
Purpose: Produce the ranked node ids for one (npc_id, query) pair, the way the ENGINE
         produces them — inside the DEC-209 scope, at the arm's rag_top_k.
Does NOT: load cases, compute metrics, print, or write artifacts.
Dependencies injected: the embedding index, the graph session and the profile are all
         arguments; engine_adapter is the sole gateway to npc_engine.
Used by: evals.retrieval_runner.

Split out of retrieval_runner.py for the 300-line cap, along a real seam: this module
answers "what does retrieval return", the runner answers "how well did it score".

THE RANKING, IN ORDER
Scoped tier-B vector hits first, then KNOWS_ABOUT events, then the NPC's own node;
deduplicated with rank order preserved. The KNOWS_ABOUT events are exactly what the
DEC-209 scope removes from the VECTOR path — tier A already carries them, so re-ranking
them there would charge every hit twice — and they remain in this list because they do
genuinely reach the model as tier-A `event:` items.

`k` IS THE METRIC WINDOW, NOT THE RETRIEVAL WIDTH. Those were the same number until P9,
which is why `--retrieval-profile wide_rag` could be recorded into retrieval_metrics.json
while the harness searched at the case's k. Retrieval width now comes from the profile.
"""

from __future__ import annotations

from typing import Any

from evals import engine_adapter

__all__ = ["retrieve_ranked_ids"]


async def _vector_hits(
    npc_id: str,
    query: str,
    profile: Any,
    embedding_index: Any,
    graph_session: Any,
    known_event_ids: set[str],
) -> list[str]:
    """Return the vector-ranked node IDs, inside the DEC-209 scope.

    The scope is the NPC's 1-hop subgraph, location and faction, MINUS the events it
    already knows. An empty scope means NO vector search — never an unfiltered one.

    Args:
        npc_id: Character node ID.
        query: Player query text.
        profile: The resolved RetrievalProfile this measurement runs under.
        embedding_index: Vector store (must have an async .search).
        graph_session: Active Neo4j AsyncSession.
        known_event_ids: Events the NPC already carries in tier A.

    Returns:
        Ranked node ID strings from the vector store; empty when the arm skips RAG or
        the NPC has no scope.
    """
    if profile.skip_rag:
        return []
    scope = await engine_adapter.rag_scope_ids(session=graph_session, npc_id=npc_id)
    scope = set(scope) - known_event_ids
    if not scope:
        return []
    hits = await embedding_index.search(
        query=query, top_k=profile.rag_top_k, filter_ids=scope
    )
    return [row["id"] for row in hits]


async def retrieve_ranked_ids(
    npc_id: str,
    query: str,
    k: int,
    profile: Any,
    embedding_index: Any,
    graph_session: Any,
) -> list[str]:
    """Return a ranked list of node IDs for one (npc_id, query) pair.

    Args:
        npc_id: Character node ID.
        query: Player query text.
        k: Metric window from the case (precision@k), NOT the retrieval width.
        profile: The resolved RetrievalProfile this measurement runs under.
        embedding_index: EmbeddingIndex instance (must have .search coroutine).
        graph_session: Active Neo4j AsyncSession.
    Returns:
        Ordered list of node ID strings (most relevant first).
    """
    known_event_ids = await engine_adapter.known_event_ids(
        session=graph_session, npc_id=npc_id
    )
    ranked = await _vector_hits(
        npc_id, query, profile, embedding_index, graph_session, set(known_event_ids)
    )

    # Append KNOWS_ABOUT event IDs (graph-sourced, not vector-ranked)
    for event_id in sorted(known_event_ids):
        if event_id not in ranked:
            ranked.append(event_id)

    # Append NPC's own character node (always Tier A)
    if npc_id not in ranked:
        ranked.append(npc_id)

    return ranked

