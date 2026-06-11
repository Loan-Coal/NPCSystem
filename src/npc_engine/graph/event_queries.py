"""
Module: event_queries
Layer: graph
Purpose: Cypher queries for event awareness seeding, location resolution, and
         player-observable event retrieval.
Does NOT: orchestrate event logic, open transactions, call LLMs, or invent new
          node/edge types beyond the existing Event + KNOWS_ABOUT schema.
Dependencies: neo4j (AsyncSession, AsyncTransaction).
Dependencies injected: AsyncSession (per read call) or AsyncTransaction (seed/write calls).
Used by: npc_engine.engines.events.event_handler,
         npc_engine.engines.events.awareness_seeder,
         npc_engine.engines.events.location_scoper,
         npc_engine.api.routes.player_events
"""

from __future__ import annotations

from typing import Any

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

CYPHER_RECENT_PLAYER_EVENTS = """
MATCH (p:Character {id: $player_id, is_player: true})-[:KNOWS_ABOUT]->(e:Event)
WHERE e.tick_id IS NOT NULL
RETURN e.id                                          AS event_id,
       e.event_type                                  AS event_type,
       coalesce(e.summary, e.event_type, '')         AS label,
       e.severity                                    AS severity,
       e.tick_id                                     AS tick_id,
       coalesce(e.location_id, '')                   AS location_id,
       coalesce(e.src_character_id, '')              AS src_character_id
ORDER BY e.tick_id DESC
LIMIT $limit
"""

_PLAYER_EVENTS_DEFAULT_LIMIT = 20
_PLAYER_EVENTS_MAX_LIMIT = 100


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


async def get_recent_player_events(
    session: AsyncSession,
    player_id: str,
    limit: int = _PLAYER_EVENTS_DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Return the most recent events observable by the given player.

    Matches Event nodes that have a KNOWS_ABOUT edge from the player Character
    node (existing event-awareness schema — no new node/edge types introduced).
    Results are ordered by tick descending.

    Does NOT: filter by knowledge_state; all KNOWS_ABOUT edges are included.
    Dependencies injected: AsyncSession.

    Args:
        session: Active Neo4j async session.
        player_id: ID of the player Character node.
        limit: Maximum number of events to return. Clamped to
               [1, _PLAYER_EVENTS_MAX_LIMIT].

    Returns:
        List of dicts with keys: event_id, event_type, label, severity,
        tick_id, location_id, src_character_id.
        Returns an empty list when the player exists but has no known events,
        or when the player node is not found.
    """
    clamped = max(1, min(limit, _PLAYER_EVENTS_MAX_LIMIT))
    result = await session.run(CYPHER_RECENT_PLAYER_EVENTS, player_id=player_id, limit=clamped)
    rows = await result.data()
    await result.consume()
    return [
        {
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "label": row["label"],
            "severity": row["severity"],
            "tick_id": row["tick_id"],
            "location_id": row["location_id"],
            "src_character_id": row["src_character_id"],
        }
        for row in rows
    ]
