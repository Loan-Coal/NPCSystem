"""
Module: faction_history_queries
Layer: graph
Purpose: Cypher queries for creating and reading FactionStandingEvent nodes.
Does NOT: implement business logic or call LLMs.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.faction_history_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_CREATE_FACTION_STANDING_EVENT = """
CREATE (fse:FactionStandingEvent {
    id:             $id,
    src_faction_id: $src_faction_id,
    dst_faction_id: $dst_faction_id,
    delta:          $delta,
    new_standing:   $new_standing,
    tick_id:        $tick_id,
    cause_event_id: $cause_event_id,
    cause_rule_id:  $cause_rule_id
})
RETURN fse.id AS id
"""

# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_STANDING_HISTORY = """
MATCH (fse:FactionStandingEvent)
WHERE fse.src_faction_id = $src_faction_id
  AND fse.dst_faction_id = $dst_faction_id
RETURN fse.id AS id,
       toInteger(fse.delta) AS delta,
       toInteger(fse.new_standing) AS new_standing,
       toInteger(fse.tick_id) AS tick_id,
       fse.cause_event_id AS cause_event_id,
       fse.cause_rule_id AS cause_rule_id
ORDER BY fse.tick_id DESC
LIMIT $limit
"""

CYPHER_GET_STANDING_TREND = """
MATCH (fse:FactionStandingEvent)
WHERE fse.src_faction_id = $src_faction_id
  AND fse.dst_faction_id = $dst_faction_id
  AND fse.tick_id >= $min_tick
RETURN toInteger(fse.tick_id) AS tick_id, toInteger(fse.delta) AS delta
ORDER BY fse.tick_id ASC
"""


async def get_standing_history(
    session: AsyncSession,
    *,
    src_faction_id: str,
    dst_faction_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch the most recent standing-change events between two factions.

    Args:
        session: Active Neo4j async session.
        src_faction_id: Source faction ID.
        dst_faction_id: Destination faction ID.
        limit: Maximum number of records to return.

    Returns:
        List of event dicts ordered by tick descending.
    """
    result = await session.run(
        CYPHER_GET_STANDING_HISTORY,
        src_faction_id=src_faction_id,
        dst_faction_id=dst_faction_id,
        limit=limit,
    )
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_raw_trend_rows(
    session: AsyncSession,
    *,
    src_faction_id: str,
    dst_faction_id: str,
    min_tick: int,
) -> list[dict[str, Any]]:
    """Fetch (tick_id, delta) pairs for trend computation.

    Args:
        session: Active Neo4j async session.
        src_faction_id: Source faction ID.
        dst_faction_id: Destination faction ID.
        min_tick: Only return events at or after this tick.

    Returns:
        List of dicts with tick_id and delta keys, ordered ascending.
    """
    result = await session.run(
        CYPHER_GET_STANDING_TREND,
        src_faction_id=src_faction_id,
        dst_faction_id=dst_faction_id,
        min_tick=min_tick,
    )
    return cast(list[dict[str, Any]], [dict(record) async for record in result])
