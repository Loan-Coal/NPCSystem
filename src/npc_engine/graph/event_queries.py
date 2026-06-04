"""
Module: event_queries
Layer: graph
Purpose: Cypher queries for event awareness seeding and location resolution.
Does NOT: orchestrate event logic, open transactions, or call LLMs.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession or AsyncTransaction.
Used by: npc_engine.engines.events.event_handler,
         npc_engine.engines.events.awareness_seeder,
         npc_engine.engines.events.location_scoper
"""

from __future__ import annotations

from neo4j import AsyncSession, AsyncTransaction

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_CHARACTERS_AT_LOCATION = """
MATCH (c:Character {is_active: true})-[:LOCATED_AT]->(loc:Location {id: $location_id})
RETURN c.id AS character_id
"""

CYPHER_SEED_AWARENESS = """
MATCH (c:Character)-[:LOCATED_AT]->(:Location {id: $location_id}), (e:Event {id: $event_id})
WHERE c.is_player = false
    AND c.is_active = true
MERGE (c)-[k:KNOWS_ABOUT]->(e)
SET k.knowledge_state = 'knows',
    k.learned_at_tick = $tick_id,
    k.distortion_type = null,
    k.distortion_level = null,
    k.distorted_summary = null,
    k.source_character_id = null
"""

CYPHER_LOCATIONS_BY_TAG = """
MATCH (loc:Location {location_tag: $location_tag})
RETURN loc.id AS id
"""


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_characters_at_location(
    session: AsyncSession,
    location_id: str,
) -> list[str]:
    """Return IDs of active characters at the given location.

    Args:
        session: Active Neo4j async session.
        location_id: ID of the Location node to query.

    Returns:
        List of character ID strings; empty list if no characters are present.
    """
    result = await session.run(CYPHER_CHARACTERS_AT_LOCATION, location_id=location_id)
    return [str(record["character_id"]) async for record in result]


async def seed_awareness_tx(
    tx: AsyncTransaction,
    event_id: str,
    location_id: str,
    tick_id: int,
) -> None:
    """Mark all active non-player NPCs at the given location as knowing the event.

    Must be called within an open transaction.

    Args:
        tx: Active Neo4j async transaction.
        event_id: Event node ID to seed awareness for.
        location_id: Location node ID scoping which characters are seeded.
        tick_id: Current game tick recorded on each KNOWS_ABOUT edge.
    """
    await tx.run(CYPHER_SEED_AWARENESS, event_id=event_id, location_id=location_id, tick_id=tick_id)


async def get_locations_by_tag(
    session: AsyncSession,
    location_tag: str,
) -> list[str]:
    """Return location IDs matching the given location tag.

    Args:
        session: Active Neo4j async session.
        location_tag: Location tag string to match against Location nodes.

    Returns:
        List of location ID strings; empty list if no matching locations exist.
    """
    result = await session.run(CYPHER_LOCATIONS_BY_TAG, location_tag=location_tag)
    return [str(record["id"]) async for record in result]
