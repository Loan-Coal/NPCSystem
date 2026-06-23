"""
Module: story_pacing_queries
Layer: graph
Purpose: Read-side Cypher for story pacing — active high-severity quests and recent major events.
Does NOT: open transactions or write to the graph.
Dependencies injected: AsyncSession (passed per call)
Dependencies: neo4j, graph.labels
Used by: engines/story_pacing/story_pacing_engine
"""
from __future__ import annotations

from typing import Any
from neo4j import AsyncSession

from npc_engine.graph.labels import EVENT, QUEST

# ---------------------------------------------------------------------------
# Query constants
# ---------------------------------------------------------------------------

CYPHER_GET_ACTIVE_HIGH_SEVERITY_QUESTS = f"""
MATCH (q:{QUEST})
WHERE q.status <> 'completed'
  AND q.severity IS NOT NULL
  AND q.severity >= $threshold
RETURN q.id AS quest_id, q.severity AS severity
"""

CYPHER_GET_RECENT_MAJOR_EVENTS = f"""
MATCH (e:{EVENT})
WHERE e.tick_id IS NOT NULL
  AND e.tick_id >= $min_tick_id
  AND e.severity >= $floor
RETURN e.id AS event_id, e.severity AS severity, e.tick_id AS tick_id
"""

# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------


async def get_active_high_severity_quests(
    session: AsyncSession, threshold: int
) -> list[dict[str, Any]]:
    """Return active quests with severity at or above the suppression threshold.

    Args:
        session: Active Neo4j async session.
        threshold: Minimum severity value for a quest to be considered high-severity.

    Returns:
        List of dicts with keys quest_id (str) and severity (int).
    """
    result = await session.run(
        CYPHER_GET_ACTIVE_HIGH_SEVERITY_QUESTS, threshold=threshold
    )
    return [
        {"quest_id": record["quest_id"], "severity": int(record["severity"])}
        async for record in result
    ]


async def get_recent_major_events(
    session: AsyncSession, min_tick_id: int, floor: int
) -> list[dict[str, Any]]:
    """Return major events that occurred at or after min_tick_id.

    Args:
        session: Active Neo4j async session.
        min_tick_id: Earliest tick ID to include in the search window.
        floor: Minimum severity for an event to be considered major.

    Returns:
        List of dicts with keys event_id (str), severity (int), and tick_id (int).
    """
    result = await session.run(
        CYPHER_GET_RECENT_MAJOR_EVENTS, min_tick_id=min_tick_id, floor=floor
    )
    return [
        {
            "event_id": record["event_id"],
            "severity": int(record["severity"]),
            "tick_id": int(record["tick_id"]),
        }
        async for record in result
    ]
