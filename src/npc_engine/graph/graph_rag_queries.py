"""
Module: graph_rag_queries
Layer: graph
Purpose: Cypher for GraphRAG retrieval — 1-hop seed expansion, and the RAG candidate
         SCOPE an NPC's tier-B search is allowed to range over (DEC-209).
Does NOT: score results or call the embedding index.
Dependencies injected: AsyncSession (caller-managed).
Used by: retrieval.graph_rag
"""
from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.infra.labels import CHARACTER, EVENT
from npc_engine.graph.infra.relationships import LOCATED_AT, MEMBER_OF

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


# DEC-209. Tier B exists to retrieve what tier A structurally cannot reach, so its
# candidate set is a SCOPE, not a whitelist: the NPC's 1-hop neighbourhood, plus
# everything standing in its location, plus everything in its faction. The caller
# subtracts the events the NPC already knows — those are already tier-A `event:` items,
# and re-ranking them in tier B charges the budget twice for one fact.
#
# The three legs are UNIONed rather than expressed as one variable-length pattern so each
# leg stays index-addressable on `id` and none of them can degrade into a store scan. The
# NPC's own node is excluded: an NPC retrieving itself is not retrieval.
_CYPHER_RAG_SCOPE_IDS = f"""
MATCH (c:{CHARACTER} {{id: $npc_id}})-[]-(neighbor)
WHERE neighbor.id IS NOT NULL AND neighbor.id <> $npc_id
RETURN DISTINCT neighbor.id AS id
UNION
MATCH (c:{CHARACTER} {{id: $npc_id}})-[:{LOCATED_AT}]->(loc)<-[:{LOCATED_AT}]-(colocated)
WHERE colocated.id IS NOT NULL AND colocated.id <> $npc_id
RETURN DISTINCT colocated.id AS id
UNION
MATCH (c:{CHARACTER} {{id: $npc_id}})-[:{MEMBER_OF}]->(f)<-[:{MEMBER_OF}]-(kin)
WHERE kin.id IS NOT NULL AND kin.id <> $npc_id
RETURN DISTINCT kin.id AS id
"""


async def get_rag_scope_ids_for_npc(session: AsyncSession, *, npc_id: str) -> set[str]:
    """Return the node ids tier-B retrieval is allowed to range over for this NPC.

    The scope is the NPC's 1-hop subgraph, its location's co-located nodes, and its
    faction's fellow members. It does NOT subtract the NPC's known events — that is the
    caller's job, because the caller already holds that set and a second read of it here
    could disagree with the one tier A was built from.

    Args:
        session: Active Neo4j async session.
        npc_id: The NPC whose scope is being computed.

    Returns:
        Set of node ids. An EMPTY set means this NPC has no RAG scope, which means no
        RAG — never an unfiltered sweep of the store.
    """
    result = await session.run(_CYPHER_RAG_SCOPE_IDS, npc_id=npc_id)
    rows = await result.data()
    return {str(row["id"]) for row in rows if row.get("id")}
