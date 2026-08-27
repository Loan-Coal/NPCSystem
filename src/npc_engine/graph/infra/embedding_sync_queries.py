"""
Module: embedding_sync_queries
Layer: graph
Purpose: Cypher queries for the embedding reconciliation worker — select stale nodes and write embeddings.
Does NOT: encode text or call external services.
Dependencies injected: AsyncSession (caller-managed).
Used by: retrieval.embedding_reconciler
"""
from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

_CYPHER_SELECT_STALE_NODES = """
MATCH (n:Character)
WHERE n.is_active = true
  AND n.id IS NOT NULL
  AND n.last_graph_updated_at IS NOT NULL
  AND (
      n.last_embedding_indexed_at IS NULL
      OR n.last_graph_updated_at > n.last_embedding_indexed_at
      OR n.embedding_model IS NULL
      OR n.embedding_model <> $embedding_model
  )
RETURN n.id AS id,
       'Character' AS kind,
       trim(coalesce(n.name, '') + ' ' + coalesce(n.archetype, '') + ' ' + coalesce(n.biography, '') + ' ' + coalesce(n.current_mood, '')) AS text,
       properties(n) AS payload
UNION ALL
MATCH (n:Event)
WHERE n.id IS NOT NULL
  AND n.last_graph_updated_at IS NOT NULL
  AND (
      n.last_embedding_indexed_at IS NULL
      OR n.last_graph_updated_at > n.last_embedding_indexed_at
      OR n.embedding_model IS NULL
      OR n.embedding_model <> $embedding_model
  )
RETURN n.id AS id,
       'Event' AS kind,
       trim(coalesce(n.summary, '') + ' ' + coalesce(n.event_type, '') + ' ' + coalesce(n.location_id, '')) AS text,
       properties(n) AS payload
UNION ALL
MATCH (n:Location)
WHERE n.id IS NOT NULL
  AND n.last_graph_updated_at IS NOT NULL
  AND (
      n.last_embedding_indexed_at IS NULL
      OR n.last_graph_updated_at > n.last_embedding_indexed_at
      OR n.embedding_model IS NULL
      OR n.embedding_model <> $embedding_model
  )
RETURN n.id AS id,
       'Location' AS kind,
       trim(coalesce(n.name, '') + ' ' + coalesce(n.descriptor, '') + ' ' + coalesce(n.region, '') + ' ' + coalesce(n.location_tag, '')) AS text,
       properties(n) AS payload
"""

# DEC-211 Decision 1: the node records WHAT PRODUCED its vector. Without this, changing
# EMBEDDING_MODEL silently invalidates every stored vector and every prior measurement,
# because the reconciler compares last_embedding_indexed_at against last_graph_updated_at
# and never model identity. This is a graph node schema change, signed off in DEC-211.
_CYPHER_BATCH_SET_EMBEDDINGS = """
UNWIND $nodes AS n
MATCH (m {id: n.id})
SET m.embedding = n.embedding,
    m.last_embedding_indexed_at = datetime(n.indexed_at),
    m.embedding_model = n.embedding_model,
    m.embedding_dim = n.embedding_dim
"""


async def select_stale_nodes(
    session: AsyncSession, batch_size: int, *, embedding_model: str = ""
) -> list[dict[str, Any]]:
    """Return up to batch_size nodes whose embeddings are stale, missing, or foreign.

    A node is stale when last_graph_updated_at > last_embedding_indexed_at, when
    last_embedding_indexed_at is NULL, or when its embedding_model differs from the
    configured one (DEC-211 Decision 2) — changing the model then re-embeds the world on
    the next ensure_corpus instead of leaving a mixed-model store that ranks nonsense.

    Args:
        session: Active Neo4j async session.
        batch_size: Maximum number of records to collect.
        embedding_model: The configured EMBEDDING_MODEL. The "" default preserves the
            pre-DEC-211 behaviour for callers that have not been updated: every node
            already carrying a model name compares unequal to "" and is treated as
            stale, which is the SAFE direction — re-embedding costs time, a mixed-model
            store costs a measurement.

    Returns:
        List of dicts with keys: node_id, kind, text, payload.
    """
    result = await session.run(_CYPHER_SELECT_STALE_NODES, embedding_model=embedding_model)
    rows: list[dict[str, Any]] = []
    try:
        async for record in result:
            if len(rows) >= batch_size:
                break
            rows.append({
                "node_id": str(record["id"] or ""),
                "kind": str(record["kind"] or ""),
                "text": str(record["text"] or "").strip(),
                "payload": dict(record["payload"] or {}),
            })
    finally:
        await result.consume()
    return rows


async def batch_set_embeddings(
    session: AsyncSession,
    nodes: list[dict[str, Any]],
) -> None:
    """Write embedding vectors and mark-indexed timestamps for a batch of nodes.

    Args:
        session: Active Neo4j async session.
        nodes: List of dicts with keys: id (str), embedding (list[float]), indexed_at (ISO str).
    """
    result = await session.run(_CYPHER_BATCH_SET_EMBEDDINGS, nodes=nodes)
    await result.consume()
