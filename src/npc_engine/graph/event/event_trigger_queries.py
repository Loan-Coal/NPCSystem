"""
Module: event_trigger_queries
Layer: graph
Purpose: Read-only Cypher queries for finding unprocessed trigger events and
         military NPCs, used by the EventQuestTrigger engine.
Does NOT: write to the graph, call LLMs, or import engine-layer code.
Dependencies: None (pure Cypher constants, session passed per call).
Dependencies injected: AsyncSession (passed per call).
Used by: npc_engine.engines.quest_generation.event_quest_trigger
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

CYPHER_UNPROCESSED_TRIGGER_EVENTS = """
MATCH (e:Event)
WHERE e.event_type IN $trigger_types
  AND NOT ((:Quest)-[:CAUSED_BY]->(e))
RETURN e.id AS event_id, e.location_id AS location_id
LIMIT $limit
"""

CYPHER_MILITARY_NPC_AT_LOCATION = """
MATCH (c:Character {is_active: true})-[:LOCATED_AT]->(loc:Location {id: $location_id})
WHERE c.archetype IN $military_archetypes
RETURN c.id AS character_id
LIMIT 1
"""

CYPHER_ANY_MILITARY_NPC = """
MATCH (c:Character {is_active: true})
WHERE c.archetype IN $military_archetypes
RETURN c.id AS character_id
LIMIT 1
"""


async def get_unprocessed_trigger_events(
    session: AsyncSession,
    trigger_types: frozenset[str],
    limit: int,
) -> list[dict[str, Any]]:
    """Return events matching trigger types that have no quest caused by them.

    Args:
        session: Active Neo4j async session.
        trigger_types: Set of event_type strings to watch for.
        limit: Maximum number of events to return per call.

    Returns:
        List of dicts with keys ``event_id`` and ``location_id``.
    """
    result = await session.run(
        CYPHER_UNPROCESSED_TRIGGER_EVENTS,
        trigger_types=list(trigger_types),
        limit=limit,
    )
    rows = [dict(r) async for r in result]
    await result.consume()
    return rows


async def get_military_npc_at_location(
    session: AsyncSession,
    location_id: str,
    military_archetypes: frozenset[str],
) -> str | None:
    """Return the ID of a military-archetype Character at the given location.

    Args:
        session: Active Neo4j async session.
        location_id: Location node ID to search within.
        military_archetypes: Set of archetype strings considered military.

    Returns:
        Character ID string, or None if no military NPC is at that location.
    """
    result = await session.run(
        CYPHER_MILITARY_NPC_AT_LOCATION,
        location_id=location_id,
        military_archetypes=list(military_archetypes),
    )
    rows = [dict(r) async for r in result]
    await result.consume()
    return str(rows[0]["character_id"]) if rows else None


async def get_any_military_npc(
    session: AsyncSession,
    military_archetypes: frozenset[str],
) -> str | None:
    """Return the ID of any active military-archetype Character (world-wide fallback).

    Args:
        session: Active Neo4j async session.
        military_archetypes: Set of archetype strings considered military.

    Returns:
        Character ID string, or None if no military NPC exists.
    """
    result = await session.run(
        CYPHER_ANY_MILITARY_NPC,
        military_archetypes=list(military_archetypes),
    )
    rows = [dict(r) async for r in result]
    await result.consume()
    return str(rows[0]["character_id"]) if rows else None
