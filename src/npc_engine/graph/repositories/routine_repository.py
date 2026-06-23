"""
Module: routine_repository
Layer: graph
Purpose: Neo4j adapter for the routine graph domain. Opens a session per operation from
         the injected GraphDB and delegates to graph.routine_queries and
         graph.location_history_service, so RoutineEngine depends on the abstraction and
         holds no session. Swap seam for cache/alternate DB/microservice backends
         (DEC-122 / SEV-24).
Does NOT: resolve schedules, contain engine logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_routine_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.db import GraphDB
from npc_engine.graph.location.location_history_service import record_departure
from npc_engine.graph.scheduling.routine_queries import (
    clear_routine_override,
    get_scheduled_characters,
    update_character_location,
)


class Neo4jRoutineRepository:
    """Session-per-call Neo4j adapter for the routine domain (RoutineGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_scheduled_characters(self) -> list[dict[str, Any]]:
        """Open a session and return active scheduled characters with their location."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_scheduled_characters(session=session)

    async def update_character_location(
        self, *, character_id: str, location_id: str, arrived_at_tick: int
    ) -> None:
        """Open a session and move a character's LOCATED_AT edge."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await update_character_location(
                session=session,
                character_id=character_id,
                location_id=location_id,
                arrived_at_tick=arrived_at_tick,
            )

    async def clear_routine_override(self, *, character_id: str) -> None:
        """Open a session and clear a character's expired routine override."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await clear_routine_override(session=session, character_id=character_id)

    async def record_departure(
        self,
        *,
        character_id: str,
        location_id: str,
        arrived_at_tick: int,
        departed_at_tick: int,
        reason: str,
    ) -> None:
        """Open a session and archive a character's stay as a WAS_AT edge."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await record_departure(
                session,
                character_id=character_id,
                location_id=location_id,
                arrived_at_tick=arrived_at_tick,
                departed_at_tick=departed_at_tick,
                reason=reason,
            )
