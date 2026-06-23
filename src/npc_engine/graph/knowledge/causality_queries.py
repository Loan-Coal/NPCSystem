"""
Module: causality_queries
Layer: graph
Purpose: Cypher query strings and read accessors for CAUSED_BY edges (event consequence provenance).
Does NOT: execute business logic or validate payloads.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.knowledge.causality_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_CREATE_CAUSED_BY = """
MATCH (effect {id: $effect_node_id}), (cause:Event {id: $cause_event_id})
CREATE (effect)-[:CAUSED_BY {
    causation_strength: $causation_strength,
    cause_type:         $cause_type,
    tick_lag:           $tick_lag
}]->(cause)
"""

# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_CONSEQUENCE_CHAIN = """
MATCH path = (root:Event {id: $root_event_id})<-[:CAUSED_BY*1..$max_depth]-(effect)
RETURN effect.id   AS node_id,
       effect.type AS node_type,
       length(path) AS depth,
       [(effect)-[e:CAUSED_BY]->(c) | {
           cause_id: c.id,
           strength: toInteger(e.causation_strength),
           cause_type: e.cause_type,
           tick_lag: toInteger(e.tick_lag)
       }][0] AS causation
ORDER BY depth ASC
"""

CYPHER_GET_CAUSES = """
MATCH (effect {id: $node_id})-[e:CAUSED_BY]->(cause:Event)
RETURN cause.id   AS cause_id,
       cause.type AS cause_type,
       toInteger(e.causation_strength) AS causation_strength,
       e.cause_type AS linkage_type,
       toInteger(e.tick_lag) AS tick_lag
"""


async def get_consequence_chain(
    session: AsyncSession,
    *,
    root_event_id: str,
    max_depth: int = 5,
) -> list[dict[str, Any]]:
    """Walk CAUSED_BY edges forward from a root event and return the causal chain.

    Args:
        session: Active Neo4j async session.
        root_event_id: ID of the originating event node.
        max_depth: Maximum edge hops to traverse.

    Returns:
        List of effect node dicts ordered by depth ascending.
    """
    result = await session.run(
        CYPHER_GET_CONSEQUENCE_CHAIN,
        root_event_id=root_event_id,
        max_depth=max_depth,
    )
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_causes(
    session: AsyncSession,
    *,
    node_id: str,
    node_type: str,
) -> list[dict[str, Any]]:
    """Return direct cause events for a given node.

    Args:
        session: Active Neo4j async session.
        node_id: ID of the effect node.
        node_type: Label of the effect node (unused in query, kept for API symmetry).

    Returns:
        List of cause event dicts.
    """
    result = await session.run(CYPHER_GET_CAUSES, node_id=node_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])
