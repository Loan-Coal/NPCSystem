"""
Module: chapter_queries
Layer: graph
Purpose: Neo4j read queries for CHAPTER, NARRATIVE_BEAT, and chapter-transition detection.
Does NOT: write to the graph or perform LLM calls.
Dependencies: neo4j AsyncSession
Dependencies injected: AsyncSession (per call).
Used by: engines/chapter/chapter_engine
"""

from __future__ import annotations

from typing import Any
import logging

from neo4j import AsyncSession


LOGGER = logging.getLogger(__name__)

CYPHER_GET_CURRENT_CHAPTER = """
MATCH (c:Chapter)
WHERE c.status = 'open'
RETURN c.id AS id, c.name AS name, c.started_at_tick AS started_at_tick,
       c.theme AS theme, c.status AS status
ORDER BY c.started_at_tick DESC
LIMIT 1
"""

CYPHER_GET_CHAPTER_EVENTS = """
MATCH (e:Event)-[:PART_OF_CHAPTER]->(c:Chapter {id: $chapter_id})
RETURN e.id AS id, e.event_type AS event_type, e.summary AS summary,
       e.severity AS severity, e.tick_id AS tick_id
ORDER BY e.tick_id DESC
"""

CYPHER_COUNT_COMPLETED_QUESTS_SINCE_TICK = """
MATCH (q:Quest)
WHERE q.status = 'completed' AND q.completed_at_tick >= $since_tick
RETURN count(q) AS quest_count
"""

CYPHER_GET_COMPLETED_QUESTS_SINCE_TICK = """
MATCH (q:Quest)
WHERE q.status = 'completed' AND q.completed_at_tick >= $since_tick
RETURN q.id AS id, q.title AS title, q.completed_at_tick AS completed_at_tick
ORDER BY q.completed_at_tick DESC
LIMIT $limit
"""

CYPHER_GET_RECENT_EVENTS_FOR_CHAPTER = """
MATCH (e:Event)
WHERE e.tick_id >= $since_tick
RETURN e.id AS id, e.event_type AS event_type, e.summary AS summary,
       e.severity AS severity, e.tick_id AS tick_id,
       coalesce(e.is_canonical, false) AS is_canonical
ORDER BY e.tick_id DESC
LIMIT $limit
"""

CYPHER_MAX_BEAT_INTENSITY_IN_CHAPTER = """
MATCH (nb:NarrativeBeat {chapter_id: $chapter_id})
RETURN coalesce(max(nb.intensity), 0) AS max_intensity
"""


async def get_current_chapter(session: AsyncSession) -> dict[str, Any] | None:
    """Return the most recently opened chapter node, or None if none is open.

    Args:
        session: Active Neo4j async session.

    Returns:
        Dict with chapter fields or None.
    """
    result = await session.run(CYPHER_GET_CURRENT_CHAPTER)
    row = await result.single()
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "started_at_tick": row["started_at_tick"],
        "theme": row["theme"],
        "status": row["status"],
    }


async def get_chapter_events(
    session: AsyncSession,
    chapter_id: str,
) -> list[dict[str, Any]]:
    """Return all events linked to a chapter via PART_OF_CHAPTER.

    Args:
        session: Active Neo4j async session.
        chapter_id: ID of the chapter.

    Returns:
        List of event dicts ordered by tick_id descending.
    """
    result = await session.run(CYPHER_GET_CHAPTER_EVENTS, chapter_id=chapter_id)
    return [
        {
            "id": rec["id"],
            "event_type": rec["event_type"],
            "summary": rec["summary"],
            "severity": rec["severity"],
            "tick_id": rec["tick_id"],
        }
        async for rec in result
    ]


async def count_completed_quests_since_tick(
    session: AsyncSession,
    since_tick: int,
) -> int:
    """Return the number of quests completed at or after since_tick.

    Args:
        session: Active Neo4j async session.
        since_tick: Minimum completed_at_tick value (inclusive).

    Returns:
        Quest count as integer.
    """
    result = await session.run(
        CYPHER_COUNT_COMPLETED_QUESTS_SINCE_TICK, since_tick=since_tick
    )
    row = await result.single()
    return int(row["quest_count"]) if row else 0


async def get_completed_quests_since_tick(
    session: AsyncSession,
    since_tick: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return recently completed quests for LLM chapter labeling context.

    Args:
        session: Active Neo4j async session.
        since_tick: Minimum completed_at_tick value (inclusive).
        limit: Maximum number of quests to return.

    Returns:
        List of quest dicts with id, title, completed_at_tick.
    """
    result = await session.run(
        CYPHER_GET_COMPLETED_QUESTS_SINCE_TICK, since_tick=since_tick, limit=limit
    )
    return [
        {
            "id": rec["id"],
            "title": rec["title"],
            "completed_at_tick": rec["completed_at_tick"],
        }
        async for rec in result
    ]


async def get_recent_events_for_chapter(
    session: AsyncSession,
    since_tick: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return recent events for LLM chapter labeling context.

    Args:
        session: Active Neo4j async session.
        since_tick: Minimum tick_id value (inclusive).
        limit: Maximum number of events to return.

    Returns:
        List of event dicts with event_type, summary, severity, is_canonical.
    """
    result = await session.run(
        CYPHER_GET_RECENT_EVENTS_FOR_CHAPTER, since_tick=since_tick, limit=limit
    )
    return [
        {
            "id": rec["id"],
            "event_type": rec["event_type"],
            "summary": rec["summary"],
            "severity": rec["severity"],
            "tick_id": rec["tick_id"],
            "is_canonical": rec["is_canonical"],
        }
        async for rec in result
    ]


async def get_max_beat_intensity_in_chapter(
    session: AsyncSession,
    chapter_id: str,
) -> int:
    """Return the maximum narrative beat intensity in a chapter (0 if no beats).

    Args:
        session: Active Neo4j async session.
        chapter_id: ID of the chapter.

    Returns:
        Maximum intensity integer (0–100).
    """
    result = await session.run(CYPHER_MAX_BEAT_INTENSITY_IN_CHAPTER, chapter_id=chapter_id)
    row = await result.single()
    return int(row["max_intensity"]) if row else 0
