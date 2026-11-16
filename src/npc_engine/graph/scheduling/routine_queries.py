"""
Module: routine_queries
Layer: graph
Purpose: Cypher queries for character routine — schedule reads, LOCATED_AT writes,
         and routine_override writes.
Does NOT: execute logic or open transactions.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.routine.routine_engine, npc_engine.engines.events.event_handler,
         npc_engine.engines.dialogue.dialogue_handler
"""

from __future__ import annotations

from typing import Any
import json

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
       c.home_location_id AS home_location_id,
       [(c)-[:LOCATED_AT]->(loc) | loc.id][0] AS current_location_id,
       [(c)-[e:LOCATED_AT]->() | e.arrived_at_tick][0] AS current_arrived_at_tick
"""

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

# Match the destination before deleting: a missing Location must leave the old edge
# in place, not strand the character with no LOCATED_AT edge (T25.7).
CYPHER_UPDATE_LOCATED_AT = """
MATCH (c:Character {id: $character_id})
MATCH (loc:Location {id: $location_id})
OPTIONAL MATCH (c)-[old:LOCATED_AT]->()
DELETE old
WITH DISTINCT c, loc
CREATE (c)-[:LOCATED_AT {arrived_at_tick: $arrived_at_tick}]->(loc)
RETURN true AS moved
"""

CYPHER_CLEAR_ROUTINE_OVERRIDE = """
MATCH (c:Character {id: $character_id})
SET c.routine_override = null
"""

CYPHER_SET_ROUTINE_OVERRIDE = """
MATCH (c:Character {id: $character_id})
SET c.routine_override = $override_json
"""


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_scheduled_characters(session: AsyncSession) -> list[dict[str, Any]]:
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
    arrived_at_tick: int = 0,
) -> bool:
    """Atomically replace the LOCATED_AT edge for a character.

    Deletes any existing LOCATED_AT edge and creates a new one pointing to
    the given location with the arrival tick stamped on the edge.
    No-op if the Location node does not exist (Cypher MATCH silently produces no rows).

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character to move.
        location_id: ID of the destination location node.
        arrived_at_tick: Tick at which the character arrived; written onto the new edge.

    Returns:
        True when the edge moved; False when the character or Location does not exist.
    """
    result = await session.run(
        CYPHER_UPDATE_LOCATED_AT,
        character_id=character_id,
        location_id=location_id,
        arrived_at_tick=arrived_at_tick,
    )
    return await result.single() is not None


async def clear_routine_override(session: AsyncSession, character_id: str) -> None:
    """Set routine_override to null on the given character.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character whose override should be cleared.
    """
    await session.run(CYPHER_CLEAR_ROUTINE_OVERRIDE, character_id=character_id)


async def set_routine_override(
    session: AsyncSession,
    character_id: str,
    location_id: str,
    expires_at_tick: int,
) -> None:
    """Write a routine_override JSON blob onto the given character.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character to override.
        location_id: Destination location the character should stay at.
        expires_at_tick: Tick number at which the override should be cleared.
    """
    override_json = json.dumps({"location_id": location_id, "expires_at_tick": expires_at_tick})
    await session.run(CYPHER_SET_ROUTINE_OVERRIDE, character_id=character_id, override_json=override_json)
