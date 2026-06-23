"""
Module: chapter_repository
Layer: graph
Purpose: Neo4j adapter for the chapter graph domain. Opens a session per operation
         from the injected GraphDB and delegates to graph.chapter_queries,
         graph.chapter_writer, and graph.faction_queries, so ChapterEngine depends on
         the abstraction and holds no session. Swap seam for cache/alternate-DB/
         microservice backends (DEC-122 / SEV-24).
Does NOT: label chapters, call LLMs, contain engine logic, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.progression.get_chapter_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.narrative.chapter_queries import (
    count_completed_quests_since_tick,
    get_completed_quests_since_tick,
    get_current_chapter,
    get_max_beat_intensity_in_chapter,
    get_recent_events_for_chapter,
)
from npc_engine.graph.narrative.chapter_writer import (
    close_chapter,
    create_chapter,
    link_event_to_chapter,
)
from npc_engine.graph.db import GraphDB
from npc_engine.graph.faction.faction_queries import get_faction_standings_summary


class Neo4jChapterRepository:
    """Session-per-call Neo4j adapter for the chapter domain (ChapterGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_current_chapter(self) -> dict[str, Any] | None:
        """Open a session and return the currently open chapter (or None)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_current_chapter(session)

    async def count_completed_quests_since_tick(self, *, since_tick: int) -> int:
        """Open a session and count quests completed at or after since_tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await count_completed_quests_since_tick(session, since_tick=since_tick)

    async def get_completed_quests_since_tick(self, *, since_tick: int) -> list[dict[str, Any]]:
        """Open a session and return quests completed at or after since_tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_completed_quests_since_tick(session, since_tick=since_tick)

    async def get_max_beat_intensity_in_chapter(self, *, chapter_id: str) -> int:
        """Open a session and return the max narrative-beat intensity in a chapter."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_max_beat_intensity_in_chapter(session, chapter_id=chapter_id)

    async def get_recent_events_for_chapter(
        self, *, since_tick: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Open a session and return recent events at or after since_tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_recent_events_for_chapter(
                session, since_tick=since_tick, limit=limit
            )

    async def get_faction_standings_summary(self, *, limit: int = 5) -> list[dict[str, Any]]:
        """Open a session and return the top factions by power_score."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_faction_standings_summary(session, limit=limit)

    async def create_chapter(
        self,
        *,
        chapter_id: str,
        name: str,
        started_at_tick: int,
        theme: str | None = None,
        status: str = "open",
    ) -> str:
        """Open a session and create/upsert a CHAPTER node; return its id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await create_chapter(
                session,
                chapter_id=chapter_id,
                name=name,
                started_at_tick=started_at_tick,
                theme=theme,
                status=status,
            )

    async def close_chapter(self, *, chapter_id: str, ended_at_tick: int) -> None:
        """Open a session and mark a chapter closed."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await close_chapter(session, chapter_id=chapter_id, ended_at_tick=ended_at_tick)

    async def link_event_to_chapter(
        self, *, event_id: str, chapter_id: str, tick_id: int
    ) -> None:
        """Open a session and create the PART_OF_CHAPTER edge (idempotent)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await link_event_to_chapter(
                session, event_id=event_id, chapter_id=chapter_id, tick_id=tick_id
            )
