"""
Module: story_pacing_repository
Layer: graph
Purpose: Neo4j adapter for the story-pacing graph reads. Opens a session per operation
         from the injected GraphDB and delegates to story_pacing_queries, so
         StoryPacingEngine depends on the abstraction and holds no session. Swap seam for
         cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: compute pacing multipliers, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_story_pacing_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.db import GraphDB
from npc_engine.graph.story_pacing_queries import (
    get_active_high_severity_quests,
    get_recent_major_events,
)


class Neo4jStoryPacingRepository:
    """Session-per-call Neo4j adapter for story-pacing reads (StoryPacingGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_active_high_severity_quests(self, *, threshold: int) -> list[dict[str, Any]]:
        """Open a session and return active quests at/above the severity threshold."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_active_high_severity_quests(session, threshold)

    async def get_recent_major_events(
        self, *, min_tick_id: int, floor: int
    ) -> list[dict[str, Any]]:
        """Open a session and return recent major events at/after min_tick_id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_recent_major_events(session, min_tick_id, floor)
