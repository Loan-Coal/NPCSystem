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
  )
RETURN n.id AS id,
       'Location' AS kind,
       trim(coalesce(n.name, '') + ' ' + coalesce(n.descriptor, '') + ' ' + coalesce(n.region, '') + ' ' + coalesce(n.location_tag, '')) AS text,
       properties(n) AS payload
"""

_CYPHER_BATCH_SET_EMBEDDINGS = """
UNWIND $nodes AS n
MATCH (m {id: n.id})
SET m.embedding = n.embedding,
    m.last_embedding_indexed_at = datetime(n.indexed_at)
"""


async def select_stale_nodes(session: AsyncSession, batch_size: int) -> list[dict[str, Any]]:
    """Return up to batch_size nodes whose embeddings are stale or missing.

    A node is stale when last_graph_updated_at > last_embedding_indexed_at or
    last_embedding_indexed_at is NULL.

    Args:
        session: Active Neo4j async session.
        batch_size: Maximum number of records to collect.

    Returns:
        List of dicts with keys: id, kind, text, payload.
    """
    result = await session.run(_CYPHER_SELECT_STALE_NODES)
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
