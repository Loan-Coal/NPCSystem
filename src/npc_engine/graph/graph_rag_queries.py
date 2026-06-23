"""
Module: graph_rag_queries
Layer: graph
Purpose: Cypher query for 1-hop graph expansion used by GraphRAG retrieval.
Does NOT: score results or call the embedding index.
Dependencies injected: AsyncSession (caller-managed).
Used by: retrieval.graph_rag
"""
from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.infra.labels import EVENT

# Seeds originate from the NPC's KNOWS_ABOUT set (Event nodes only — see
# graph_reader.get_known_event_ids_for_npc), so the seed match is label-filtered
# to :Event. This avoids the full-node scan flagged in ISSUE-056 and prevents
# anchoring expansion on unintended node types. (DEC-093: the schema has no
# :Knowledge label, so the roadmap's `Event|Knowledge` reduces to :Event.)
_CYPHER_EXPAND_SEEDS = f"""
UNWIND $seed_ids AS seed_id
MATCH (seed:{EVENT}) WHERE seed.id = seed_id
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


async def expand_seeds(
    session: AsyncSession,
    seed_ids: list[str],
    edge_types: list[str],
) -> list[dict[str, Any]]:
    """Expand seed node IDs 1 hop along the given edge types and return neighbor rows.

    Args:
        session: Active Neo4j async session.
        seed_ids: IDs of the seed nodes to expand from.
        edge_types: Edge type strings to traverse (e.g. KNOWS_ABOUT, CAUSED_BY).

    Returns:
        List of dicts with keys: seed_id, neighbor_id, neighbor_props, edge_type, edge_weight.
    """
    result = await session.run(_CYPHER_EXPAND_SEEDS, seed_ids=seed_ids, edge_types=edge_types)
    return await result.data()
