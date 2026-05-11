"""
Module: routine_queries
Layer: engines/routine
Purpose: Cypher queries for the routine engine — character schedule reads and LOCATED_AT writes.
Does NOT: execute logic or open transactions.
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.routine.routine_engine
"""

from __future__ import annotations

from neo4j import AsyncSession


# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_SCHEDULED_CHARACTERS = """
MATCH (c:Character)-[:FOLLOWS_SCHEDULE]->(s:Schedule)
WHERE c.is_active = true
RETURN c.id AS character_id,
       s.entries AS entries_json,
       c.routine_override AS routine_override,
       [(c)-[:LOCATED_AT]->(loc) | loc.id][0] AS current_location_id
"""

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_UPDATE_LOCATED_AT = """
MATCH (c:Character {id: $character_id})
OPTIONAL MATCH (c)-[old:LOCATED_AT]->()
DELETE old
WITH c
MATCH (loc:Location {id: $location_id})
CREATE (c)-[:LOCATED_AT]->(loc)
"""

CYPHER_CLEAR_ROUTINE_OVERRIDE = """
MATCH (c:Character {id: $character_id})
SET c.routine_override = null
"""


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_scheduled_characters(session: AsyncSession) -> list[dict]:
    """Return all active characters that follow a schedule.

    Each row includes the character ID, schedule entries JSON, current location,
    and the raw routine_override JSON string (or None).

    Args:
        session: Active Neo4j async session.

    Returns:
        List of dicts with keys character_id, entries_json, current_location_id,
        routine_override.
    """
    result = await session.run(CYPHER_GET_SCHEDULED_CHARACTERS)
    return [record.data() async for record in result]


async def update_character_location(
    session: AsyncSession,
    character_id: str,
    location_id: str,
) -> None:
    """Atomically replace the LOCATED_AT edge for a character.

    Deletes any existing LOCATED_AT edge and creates a new one pointing to
    the given location. No-op if the Location node does not exist (Cypher
    MATCH silently produces no rows).

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character to move.
        location_id: ID of the destination location node.
    """
    await session.run(
        CYPHER_UPDATE_LOCATED_AT,
        character_id=character_id,
        location_id=location_id,
    )


async def clear_routine_override(session: AsyncSession, character_id: str) -> None:
    """Set routine_override to null on the given character.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character whose override should be cleared.
    """
    await session.run(CYPHER_CLEAR_ROUTINE_OVERRIDE, character_id=character_id)
