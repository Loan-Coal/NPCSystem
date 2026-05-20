"""
Module: chapter_writer
Layer: graph
Purpose: Neo4j write operations for CHAPTER, NARRATIVE_BEAT, and PART_OF_CHAPTER edges.
Does NOT: read from the graph or perform LLM calls.
Dependencies: neo4j AsyncSession
Dependencies injected: AsyncSession (per call).
Used by: engines/chapter/chapter_engine
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession


LOGGER = logging.getLogger(__name__)

CYPHER_CREATE_CHAPTER = """
MERGE (c:Chapter {id: $id})
  ON CREATE SET
    c.name = $name,
    c.started_at_tick = $started_at_tick,
    c.theme = $theme,
    c.status = $status,
    c.ended_at_tick = null
RETURN c.id AS chapter_id
"""

CYPHER_CLOSE_CHAPTER = """
MATCH (c:Chapter {id: $chapter_id})
SET c.ended_at_tick = $ended_at_tick, c.status = 'closed'
"""

CYPHER_CREATE_NARRATIVE_BEAT = """
MERGE (nb:NarrativeBeat {id: $id})
  ON CREATE SET
    nb.kind = $kind,
    nb.intensity = $intensity,
    nb.chapter_id = $chapter_id
RETURN nb.id AS beat_id
"""

CYPHER_LINK_EVENT_TO_CHAPTER = """
MATCH (e:Event {id: $event_id}), (c:Chapter {id: $chapter_id})
MERGE (e)-[r:PART_OF_CHAPTER]->(c)
  ON CREATE SET r.linked_at_tick = $tick_id
"""


async def create_chapter(
    session: AsyncSession,
    *,
    chapter_id: str,
    name: str,
    started_at_tick: int,
    theme: str | None = None,
    status: str = "open",
) -> str:
    """Create or upsert a CHAPTER node.

    Args:
        session: Active Neo4j async session.
        chapter_id: Unique chapter ID.
        name: Human-readable chapter title.
        started_at_tick: Tick at which this chapter opened.
        theme: Optional theme label (e.g. "betrayal", "war").
        status: Chapter lifecycle status; default "open".

    Returns:
        The chapter ID (same as input chapter_id).
    """
    await session.run(
        CYPHER_CREATE_CHAPTER,
        id=chapter_id,
        name=name,
        started_at_tick=started_at_tick,
        theme=theme,
        status=status,
    )
    LOGGER.info("Created chapter %s: %r (tick=%d)", chapter_id, name, started_at_tick)
    return chapter_id


async def close_chapter(
    session: AsyncSession,
    *,
    chapter_id: str,
    ended_at_tick: int,
) -> None:
    """Mark a chapter as closed by setting ended_at_tick and status='closed'.

    Args:
        session: Active Neo4j async session.
        chapter_id: ID of the chapter to close.
        ended_at_tick: Tick at which the chapter ended.
    """
    await session.run(
        CYPHER_CLOSE_CHAPTER,
        chapter_id=chapter_id,
        ended_at_tick=ended_at_tick,
    )
    LOGGER.info("Closed chapter %s at tick %d", chapter_id, ended_at_tick)


async def create_narrative_beat(
    session: AsyncSession,
    *,
    beat_id: str,
    kind: str,
    intensity: int,
    chapter_id: str,
) -> str:
    """Create a NARRATIVE_BEAT node linked to a chapter.

    Args:
        session: Active Neo4j async session.
        beat_id: Unique beat ID.
        kind: Beat type — one of rising | climax | falling | denouement.
        intensity: Beat intensity (0–100).
        chapter_id: ID of the owning chapter.

    Returns:
        The beat ID (same as input beat_id).
    """
    await session.run(
        CYPHER_CREATE_NARRATIVE_BEAT,
        id=beat_id,
        kind=kind,
        intensity=intensity,
        chapter_id=chapter_id,
    )
    return beat_id


async def link_event_to_chapter(
    session: AsyncSession,
    *,
    event_id: str,
    chapter_id: str,
    tick_id: int,
) -> None:
    """Create a PART_OF_CHAPTER edge from an Event to a Chapter.

    Idempotent — MERGE skips duplicate edges.

    Args:
        session: Active Neo4j async session.
        event_id: ID of the Event node.
        chapter_id: ID of the Chapter node.
        tick_id: Current tick for the linked_at_tick edge property.
    """
    await session.run(
        CYPHER_LINK_EVENT_TO_CHAPTER,
        event_id=event_id,
        chapter_id=chapter_id,
        tick_id=tick_id,
    )
