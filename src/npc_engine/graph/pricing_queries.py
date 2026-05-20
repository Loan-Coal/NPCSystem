"""
Module: pricing_queries
Layer: graph
Purpose: Read-only Cypher constants for economy price lookups.
Does NOT: execute write operations or open transactions.
Dependencies injected: AsyncSession (at call site).
Used by: npc_engine.engines.economy.trade_engine
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.graph.generic_graph_utils import to_native


CYPHER_GET_CHARACTER_LOCATION_TYPE = """
MATCH (c:Character {id: $character_id})-[:AT]->(l:Location)
RETURN l.location_type AS location_type
"""

CYPHER_GET_ACTIVE_EVENTS_AT_LOCATION = """
MATCH (l:Location {id: $location_id})<-[:OCCURRED_AT]-(e:Event)
WHERE e.tick >= $since_tick
RETURN e.type AS event_type
"""

CYPHER_CHECK_FACTION_MEMBERSHIP = """
MATCH (a:Character {id: $character_id_a})-[:MEMBER_OF]->(f:Faction)<-[:MEMBER_OF]-(b:Character {id: $character_id_b})
RETURN count(f) AS shared_count
"""

CYPHER_GET_CHARACTER_LOCATION_ID = """
MATCH (c:Character {id: $character_id})-[:AT]->(l:Location)
RETURN l.id AS location_id
"""


async def get_character_location_type(session: AsyncSession, character_id: str) -> str | None:
    """Fetch the location_type of the location a character is currently at.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.

    Returns:
        The location_type string, or None if the character has no AT edge.
    """
    result = await session.run(CYPHER_GET_CHARACTER_LOCATION_TYPE, character_id=character_id)
    record = await result.single()
    if record is None:
        return None
    raw = record["location_type"]
    return str(to_native(raw)) if raw is not None else None


async def get_active_event_types_at_location(
    session: AsyncSession, location_id: str, since_tick: int
) -> list[str]:
    """Fetch distinct event types that occurred at a location within a tick window.

    Args:
        session: Active Neo4j async session.
        location_id: ID of the Location node.
        since_tick: Only events with tick >= this value are included.

    Returns:
        List of event_type strings for events at the location.
    """
    result = await session.run(
        CYPHER_GET_ACTIVE_EVENTS_AT_LOCATION,
        location_id=location_id,
        since_tick=since_tick,
    )
    return [str(to_native(record["event_type"])) async for record in result if record["event_type"] is not None]


async def check_faction_membership(
    session: AsyncSession, character_id_a: str, character_id_b: str
) -> bool:
    """Check whether two characters share at least one common faction.

    Args:
        session: Active Neo4j async session.
        character_id_a: ID of the first character.
        character_id_b: ID of the second character.

    Returns:
        True if both characters are members of at least one shared faction.
    """
    result = await session.run(
        CYPHER_CHECK_FACTION_MEMBERSHIP,
        character_id_a=character_id_a,
        character_id_b=character_id_b,
    )
    record = await result.single()
    if record is None:
        return False
    return int(record["shared_count"]) > 0


async def get_character_location_id(session: AsyncSession, character_id: str) -> str | None:
    """Fetch the location ID of the location a character is currently at.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.

    Returns:
        The location ID string, or None if the character has no AT edge.
    """
    result = await session.run(CYPHER_GET_CHARACTER_LOCATION_ID, character_id=character_id)
    record = await result.single()
    if record is None:
        return None
    raw = record["location_id"]
    return str(to_native(raw)) if raw is not None else None
