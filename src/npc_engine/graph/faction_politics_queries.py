"""
Module: faction_politics_queries
Layer: graph
Purpose: Cypher read queries for faction politics engine — recent events,
         character faction membership, and all faction standings.
Does NOT: write to the graph, open transactions, or call LLMs.
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.faction_politics.faction_politics_engine
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

_DEFAULT_EVENT_LIMIT = 20

CYPHER_GET_RECENT_EVENTS = """
MATCH (e:Event)
WHERE e.src_character_id IS NOT NULL
  AND e.event_type IS NOT NULL
RETURN e.id AS event_id, e.event_type AS event_type, e.src_character_id AS src_character_id
ORDER BY e.tick_id DESC
LIMIT $limit
"""

CYPHER_GET_CHARACTER_FACTIONS = """
MATCH (c:Character {id: $character_id})-[:MEMBER_OF]->(f:Faction)
WHERE f.is_active = true
RETURN f.id AS faction_id
"""

CYPHER_GET_ALL_STANDINGS = """
MATCH (a:Faction)-[r:STANDS_WITH]->(b:Faction)
RETURN a.id AS src_id, b.id AS dst_id, r.standing AS standing
"""


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_recent_events(
    session: AsyncSession,
    limit: int = _DEFAULT_EVENT_LIMIT,
) -> list[dict[str, str]]:
    """Return the most recent events that have a src_character_id and event_type.

    Args:
        session: Active Neo4j async session.
        limit: Maximum number of events to return (default 20).

    Returns:
        List of dicts with keys event_id, event_type, src_character_id.
    """
    result = await session.run(CYPHER_GET_RECENT_EVENTS, limit=limit)
    return [
        {
            "event_id": r["event_id"],
            "event_type": r["event_type"],
            "src_character_id": r["src_character_id"],
        }
        async for r in result
    ]


async def get_character_factions(
    session: AsyncSession,
    character_id: str,
) -> list[str]:
    """Return faction IDs the character belongs to (active factions only).

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.

    Returns:
        List of faction ID strings.
    """
    result = await session.run(CYPHER_GET_CHARACTER_FACTIONS, character_id=character_id)
    return [str(r["faction_id"]) async for r in result]


async def get_all_standings(
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """Fetch all STANDS_WITH edges from the graph.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of dicts with keys src_id, dst_id, standing.
    """
    result = await session.run(CYPHER_GET_ALL_STANDINGS)
    return [
        {"src_id": r["src_id"], "dst_id": r["dst_id"], "standing": int(r["standing"])}
        async for r in result
    ]
