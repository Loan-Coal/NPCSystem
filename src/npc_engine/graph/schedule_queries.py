"""
Module: schedule_queries
Layer: graph
Purpose: Read-only Cypher accessors for Schedule nodes and FOLLOWS_SCHEDULE edges.
Does NOT: execute write operations or open transactions.
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.schedule_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

from npc_engine.graph.generic.generic_graph_utils import to_native

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_GET_SCHEDULE = """
MATCH (s:Schedule {id: $schedule_id})
RETURN properties(s) AS schedule
"""

CYPHER_GET_CHARACTER_SCHEDULE = """
MATCH (c:Character {id: $character_id})-[:FOLLOWS_SCHEDULE]->(s:Schedule)
WHERE c.is_active = true
RETURN properties(s) AS schedule
"""

CYPHER_GET_CHARACTERS_AT_LOCATION = """
MATCH (c:Character)-[:FOLLOWS_SCHEDULE]->(s:Schedule)
WHERE c.is_active = true
  AND any(entry IN apoc.convert.fromJsonList(s.entries)
          WHERE entry.time_of_day = $time_of_day
            AND entry.location_id = $location_id)
RETURN c.id AS character_id
"""

CYPHER_GET_CHARACTER_LOCATION_AT = """
MATCH (c:Character {id: $character_id})-[:FOLLOWS_SCHEDULE]->(s:Schedule)
WHERE c.is_active = true
RETURN s.entries AS entries_json
"""

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_schedule(session: AsyncSession, schedule_id: str) -> dict[str, Any] | None:
    """Fetch a Schedule node by ID.

    Args:
        session: Active Neo4j async session.
        schedule_id: ID of the schedule node.

    Returns:
        Dict of schedule properties, or None if not found.
    """
    result = await session.run(CYPHER_GET_SCHEDULE, schedule_id=schedule_id)
    record = await result.single()
    if record is None:
        return None
    return cast(dict[str, Any], to_native(record["schedule"]))


async def get_character_schedule(
    session: AsyncSession, character_id: str
) -> dict[str, Any] | None:
    """Fetch the Schedule a character follows, or None if unassigned.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.

    Returns:
        Dict of schedule properties, or None if the character has no schedule.
    """
    result = await session.run(CYPHER_GET_CHARACTER_SCHEDULE, character_id=character_id)
    record = await result.single()
    if record is None:
        return None
    return cast(dict[str, Any], to_native(record["schedule"]))


async def get_character_location_at(
    session: AsyncSession,
    character_id: str,
    time_of_day: str,
) -> str | None:
    """Return the location_id from a character's schedule at a given time of day.

    Parses the ``entries`` JSON array on the Schedule node and returns the
    location_id for the matching time_of_day entry.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        time_of_day: One of morning | midday | afternoon | evening | night.

    Returns:
        location_id string, or None if no entry matches the time_of_day or
        the character has no schedule.
    """
    import json

    result = await session.run(CYPHER_GET_CHARACTER_LOCATION_AT, character_id=character_id)
    record = await result.single()
    if record is None:
        return None
    try:
        entries = json.loads(record["entries_json"])
    except (TypeError, ValueError):
        return None
    for entry in entries:
        if entry.get("time_of_day") == time_of_day:
            return cast(str, entry.get("location_id"))
    return None


async def get_characters_at_location(
    session: AsyncSession,
    location_id: str,
    time_of_day: str,
) -> list[str]:
    """Return character IDs scheduled to be at a location at a given time of day.

    Uses a full scan of Schedule nodes — suitable for small worlds. Does not
    rely on APOC; filtering is performed in Python after fetching all schedules.

    Args:
        session: Active Neo4j async session.
        location_id: ID of the location node.
        time_of_day: One of morning | midday | afternoon | evening | night.

    Returns:
        List of character IDs scheduled at the location for that time.
    """
    import json

    cypher = """
    MATCH (c:Character)-[:FOLLOWS_SCHEDULE]->(s:Schedule)
    WHERE c.is_active = true
    RETURN c.id AS character_id, s.entries AS entries_json
    """
    result = await session.run(cypher)
    character_ids: list[str] = []
    async for record in result:
        try:
            entries = json.loads(record["entries_json"])
        except (TypeError, ValueError):
            continue
        for entry in entries:
            if (
                entry.get("time_of_day") == time_of_day
                and entry.get("location_id") == location_id
            ):
                character_ids.append(cast(str, record["character_id"]))
                break
    return character_ids
