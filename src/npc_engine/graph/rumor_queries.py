"""
Module: rumor_queries
Layer: graph
Purpose: Cypher query strings and read accessors for Rumor nodes and BELIEVES_RUMOR edges.
Does NOT: execute business logic or validate payloads.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.rumor_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_MERGE_ROOT_RUMOR = """
MERGE (r:Rumor {id: $rumor_id})
ON CREATE SET r.content = $content,
              r.origin_event_id = $origin_event_id,
              r.created_at_tick = $created_at_tick,
              r.mutation_distance = 0,
              r.severity = $severity,
              r.is_fabricated = $is_fabricated
RETURN r.id AS id
"""

CYPHER_CREATE_DERIVED_RUMOR = """
MATCH (parent:Rumor {id: $parent_rumor_id})
CREATE (r:Rumor {
    id:                $rumor_id,
    content:           $content,
    origin_event_id:   parent.origin_event_id,
    created_at_tick:   $created_at_tick,
    mutation_distance: parent.mutation_distance + 1,
    severity:          parent.severity,
    is_fabricated:     false
})-[:DERIVED_FROM {mutation_type: $mutation_type, created_at_tick: $created_at_tick}]->(parent)
RETURN r.id AS id
"""

CYPHER_BELIEVE_RUMOR = """
MATCH (c:Character {id: $character_id}), (r:Rumor {id: $rumor_id})
MERGE (c)-[b:BELIEVES_RUMOR]->(r)
SET b.confidence = $confidence,
    b.believed_at_tick = $tick,
    b.from_character_id = $from_character_id
"""

# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_RUMORS_FOR_CHARACTER = """
MATCH (c:Character {id: $character_id})-[b:BELIEVES_RUMOR]->(r:Rumor)
WHERE b.confidence >= $min_confidence
RETURN r.id AS id,
       r.content AS content,
       toInteger(r.mutation_distance) AS mutation_distance,
       toInteger(r.severity) AS severity,
       r.is_fabricated AS is_fabricated,
       r.origin_event_id AS origin_event_id,
       toInteger(b.confidence) AS confidence,
       toInteger(b.believed_at_tick) AS believed_at_tick,
       b.from_character_id AS from_character_id
ORDER BY b.confidence DESC
"""

CYPHER_GET_RUMOR_TREE = """
MATCH (root:Rumor {id: $rumor_id})
OPTIONAL MATCH p = (child:Rumor)-[:DERIVED_FROM*1..5]->(root)
RETURN child.id AS id,
       child.content AS content,
       toInteger(child.mutation_distance) AS mutation_distance,
       length(p) AS depth
ORDER BY depth ASC
"""

CYPHER_GET_RUMOR_BELIEVERS = """
MATCH (c:Character)-[b:BELIEVES_RUMOR]->(r:Rumor {id: $rumor_id})
RETURN c.id AS character_id,
       c.name AS character_name,
       toInteger(b.confidence) AS confidence,
       toInteger(b.believed_at_tick) AS believed_at_tick
"""

CYPHER_GET_RUMORS_ABOUT_EVENT = """
MATCH (r:Rumor {origin_event_id: $event_id})
RETURN r.id AS id,
       r.content AS content,
       toInteger(r.mutation_distance) AS mutation_distance,
       toInteger(r.severity) AS severity,
       r.is_fabricated AS is_fabricated
"""


async def get_rumors_for_character(
    session: AsyncSession,
    *,
    character_id: str,
    min_confidence: int = 0,
) -> list[dict[str, Any]]:
    """Fetch rumors a character believes, ordered by confidence descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        min_confidence: Minimum confidence level to include (0–100).

    Returns:
        List of rumor belief dicts.
    """
    result = await session.run(
        CYPHER_GET_RUMORS_FOR_CHARACTER,
        character_id=character_id,
        min_confidence=min_confidence,
    )
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_rumor_tree(
    session: AsyncSession,
    *,
    rumor_id: str,
) -> list[dict[str, Any]]:
    """Fetch child rumors derived from a root rumor.

    Args:
        session: Active Neo4j async session.
        rumor_id: ID of the root Rumor node.

    Returns:
        List of derived rumor dicts ordered by depth.
    """
    result = await session.run(CYPHER_GET_RUMOR_TREE, rumor_id=rumor_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_rumor_believers(
    session: AsyncSession,
    *,
    rumor_id: str,
) -> list[dict[str, Any]]:
    """Fetch characters who believe a rumor.

    Args:
        session: Active Neo4j async session.
        rumor_id: ID of the Rumor node.

    Returns:
        List of believer dicts with confidence and tick.
    """
    result = await session.run(CYPHER_GET_RUMOR_BELIEVERS, rumor_id=rumor_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_rumors_about_event(
    session: AsyncSession,
    *,
    event_id: str,
) -> list[dict[str, Any]]:
    """Fetch rumor nodes that originated from a specific event.

    Args:
        session: Active Neo4j async session.
        event_id: ID of the originating Event node.

    Returns:
        List of rumor dicts.
    """
    result = await session.run(CYPHER_GET_RUMORS_ABOUT_EVENT, event_id=event_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])
