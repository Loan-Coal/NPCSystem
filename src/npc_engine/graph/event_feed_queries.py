"""
Module: event_feed_queries
Layer: graph
Purpose: Read-only Cypher query for the WORLD panel event feed — returns recent
         Event nodes ordered by tick descending.
Does NOT: write to Neo4j, mutate state, or call the LLM.
Dependencies: neo4j (AsyncSession)
Dependencies injected: AsyncSession (per call).
Used by: npc_engine.api.routes.system (GET /v1/system/events)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

_CYPHER_RECENT_EVENTS = """
MATCH (e:Event)
WHERE e.tick_id IS NOT NULL
RETURN e.id            AS event_id,
       e.event_type    AS event_type,
       coalesce(e.summary, e.event_type, '') AS label,
       e.severity      AS severity,
       e.tick_id       AS tick_id,
       coalesce(e.location_id, '')       AS location_id,
       coalesce(e.src_character_id, '')  AS src_character_id
ORDER BY e.tick_id DESC
LIMIT $limit
"""

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


async def get_recent_event_feed(
    session: AsyncSession,
    limit: int = _DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Return the most recent Event nodes ordered by tick descending.

    Args:
        session: Active Neo4j async session.
        limit: Maximum number of events to return. Clamped to [1, 100].
    Returns:
        List of dicts with keys: event_id, event_type, label, severity,
        tick_id, location_id, src_character_id.
    """
    clamped = max(1, min(limit, _MAX_LIMIT))
    result = await session.run(_CYPHER_RECENT_EVENTS, limit=clamped)
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
