"""
Module: location_history_queries
Layer: graph
Purpose: Cypher query strings and read accessors for WAS_AT edges (character location history).
Does NOT: execute business logic or validate payloads.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.location_history_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_CREATE_WAS_AT = """
MATCH (c:Character {id: $character_id}), (l:Location {id: $location_id})
CREATE (c)-[:WAS_AT {
    arrived_at_tick:  $arrived_at_tick,
    departed_at_tick: $departed_at_tick,
    reason:           $reason,
    tick_duration:    $tick_duration
}]->(l)
"""

CYPHER_DELETE_OLD_WAS_AT = """
MATCH (c:Character {id: $character_id})-[e:WAS_AT]->(l:Location)
WHERE e.departed_at_tick < $older_than_tick
DELETE e
RETURN count(e) AS deleted
"""

# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_LOCATION_HISTORY = """
MATCH (c:Character {id: $character_id})-[e:WAS_AT]->(l:Location)
RETURN l.id AS location_id,
       l.name AS location_name,
       toInteger(e.arrived_at_tick) AS arrived_at_tick,
       toInteger(e.departed_at_tick) AS departed_at_tick,
       e.reason AS reason,
       toInteger(e.tick_duration) AS tick_duration
ORDER BY e.departed_at_tick DESC
LIMIT $limit
"""

CYPHER_GET_ALIBI_WINDOW = """
MATCH (c:Character {id: $character_id})-[e:WAS_AT]->(l:Location)
WHERE e.arrived_at_tick <= $to_tick
  AND e.departed_at_tick >= $from_tick
RETURN l.id AS location_id,
       l.name AS location_name,
       toInteger(e.arrived_at_tick) AS arrived_at_tick,
       toInteger(e.departed_at_tick) AS departed_at_tick,
       e.reason AS reason,
       toInteger(e.tick_duration) AS tick_duration
ORDER BY e.arrived_at_tick ASC
"""


async def get_location_history(
    session: AsyncSession,
    *,
    character_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Fetch recent WAS_AT edges for a character in reverse chronological order.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        limit: Maximum number of history records to return.

    Returns:
        List of location history dicts ordered by most recent departure first.
    """
    result = await session.run(
        CYPHER_GET_LOCATION_HISTORY,
        character_id=character_id,
        limit=limit,
    )
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_alibi_window(
    session: AsyncSession,
    *,
    character_id: str,
    from_tick: int,
    to_tick: int,
) -> list[dict[str, Any]]:
    """Fetch WAS_AT edges overlapping a tick window for alibi checking.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        from_tick: Start of the tick window (inclusive).
        to_tick: End of the tick window (inclusive).

    Returns:
        List of location records ordered by arrival tick ascending.
    """
    result = await session.run(
        CYPHER_GET_ALIBI_WINDOW,
        character_id=character_id,
        from_tick=from_tick,
        to_tick=to_tick,
    )
    return cast(list[dict[str, Any]], [dict(record) async for record in result])
