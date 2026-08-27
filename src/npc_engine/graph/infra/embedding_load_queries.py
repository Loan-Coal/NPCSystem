"""
Module: embedding_load_queries
Layer: graph
Purpose: Cypher that READS persisted embeddings back out of Neo4j so the vector store can
         be populated from them — the load half of the embedding sync pair.
Does NOT: encode text, write embeddings, or touch the vector store.
Dependencies injected: AsyncSession (caller-managed).
Used by: retrieval.embedding.corpus
"""
from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.infra.labels import CHARACTER, EVENT, LOCATION

__all__ = ["count_nodes_missing_embedding", "select_embedded_nodes"]

# Payload is projected FIELD BY FIELD rather than as properties(n) (DEC-208). A
# properties(n) payload drags the 384-float embedding itself, the wall-clock indexing
# timestamps and every internal bookkeeping property into a dict that ends up serialized
# into the prompt, and stripping them again downstream is a second list to keep in sync
# with this one. What the prompt may see is decided here, once.
#
# ORDER BY id is load-bearing, not cosmetic: select_stale_nodes has no ordering and caps
# at batch_size, which makes a partially-populated corpus depend on Neo4j row order. A
# corpus whose membership is undefined is an unfalsifiable A/B input.
_CYPHER_SELECT_EMBEDDED_NODES = f"""
CALL {{
    MATCH (n:{CHARACTER})
    WHERE n.embedding IS NOT NULL AND n.id IS NOT NULL
    RETURN n.id AS node_id, '{CHARACTER}' AS kind, n.embedding AS embedding,
           n.embedding_model AS embedding_model, n.embedding_dim AS embedding_dim,
           {{id: n.id, name: n.name, archetype: n.archetype,
             biography: n.biography, current_mood: n.current_mood}} AS payload
    UNION
    MATCH (n:{EVENT})
    WHERE n.embedding IS NOT NULL AND n.id IS NOT NULL
    RETURN n.id AS node_id, '{EVENT}' AS kind, n.embedding AS embedding,
           n.embedding_model AS embedding_model, n.embedding_dim AS embedding_dim,
           {{id: n.id, summary: n.summary, event_type: n.event_type,
             severity: n.severity, occurred_at: n.occurred_at,
             location_id: n.location_id}} AS payload
    UNION
    MATCH (n:{LOCATION})
    WHERE n.embedding IS NOT NULL AND n.id IS NOT NULL
    RETURN n.id AS node_id, '{LOCATION}' AS kind, n.embedding AS embedding,
           n.embedding_model AS embedding_model, n.embedding_dim AS embedding_dim,
           {{id: n.id, name: n.name, descriptor: n.descriptor,
             region: n.region, location_tag: n.location_tag}} AS payload
}}
WITH node_id, kind, embedding, embedding_model, embedding_dim, payload
WHERE $node_ids IS NULL OR node_id IN $node_ids
RETURN node_id, kind, embedding, embedding_model, embedding_dim, payload
ORDER BY node_id
SKIP $skip LIMIT $limit
"""

_CYPHER_COUNT_MISSING_EMBEDDING = f"""
CALL {{
    MATCH (n:{CHARACTER}) WHERE n.id IS NOT NULL AND n.embedding IS NULL RETURN n.id AS node_id
    UNION
    MATCH (n:{EVENT}) WHERE n.id IS NOT NULL AND n.embedding IS NULL RETURN n.id AS node_id
    UNION
    MATCH (n:{LOCATION}) WHERE n.id IS NOT NULL AND n.embedding IS NULL RETURN n.id AS node_id
}}
RETURN count(node_id) AS missing
"""


async def select_embedded_nodes(
    session: AsyncSession, *, skip: int, limit: int, node_ids: list[str] | None = None
) -> list[dict[str, Any]]:
    """Return one deterministically ordered page of nodes that carry an embedding.

    Args:
        session: Active Neo4j async session.
        skip: Number of rows to skip; pages are stable because the query orders by id.
        limit: Maximum rows in this page; must be greater than 0.
        node_ids: When given, restrict the result to these ids — the incremental-upsert
            path refreshing one node (DEC-210). None means the whole corpus.

    Returns:
        List of dicts with keys: node_id, kind, embedding, embedding_model,
        embedding_dim, payload. The embedding is returned SEPARATELY from the payload,
        so a caller cannot accidentally serialize a 384-float vector into a prompt.

    Raises:
        ValueError: If limit is not greater than 0.
    """
    if limit <= 0:
        raise ValueError("limit must be greater than 0")
    result = await session.run(
        _CYPHER_SELECT_EMBEDDED_NODES, skip=skip, limit=limit, node_ids=node_ids
    )
    rows: list[dict[str, Any]] = []
    try:
        async for record in result:
            rows.append({
                "node_id": str(record["node_id"] or ""),
                "kind": str(record["kind"] or ""),
                "embedding": [float(value) for value in (record["embedding"] or [])],
                "embedding_model": record["embedding_model"],
                "embedding_dim": record["embedding_dim"],
                "payload": dict(record["payload"] or {}),
            })
    finally:
        await result.consume()
    return rows


async def count_nodes_missing_embedding(session: AsyncSession) -> int:
    """Return how many embeddable nodes still carry no embedding.

    Reported rather than repaired: after reconcile-until-dry this should be 0, and a
    non-zero value means the reconciler declared itself done over nodes it could not
    embed. Silently populating a partial corpus is the failure mode DEC-208 exists to
    close, so the number is surfaced in the report instead.

    Args:
        session: Active Neo4j async session.

    Returns:
        Count of Character, Event and Location nodes with no embedding property.
    """
    result = await session.run(_CYPHER_COUNT_MISSING_EMBEDDING)
    record = await result.single()
    await result.consume()
    return int(record["missing"]) if record is not None else 0
