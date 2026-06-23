"""
Module: planning_repository
Layer: graph
Purpose: Neo4j adapter for the planning graph domain. Opens a session per call from the
         injected GraphDB and delegates to need_queries / goal_service / goal_targets_writer
         / routine_queries, so the planning engines depend on the PlanningGraphPort
         abstraction and hold no session. Swap seam for cache/alternate DB/microservice
         backends (DEC-122 / SEV-24).
Does NOT: compute urgency/priority, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_goal_formation_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.needs_goals.goal_service import create_goal
from npc_engine.graph.needs_goals.goal_targets_writer import create_goal_targets_edge
from npc_engine.graph.needs_goals.need_queries import (
    get_needs_for_character,
    get_satisfying_location_for_need,
)
from npc_engine.graph.scheduling.routine_queries import update_character_location
from npc_engine.world.time_utils import TimePoint


class Neo4jPlanningRepository:
    """Session-per-call Neo4j adapter for GOAP planning (PlanningGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_needs_for_character(self, *, character_id: str) -> list[dict[str, Any]]:
        """Open a session and return all Need nodes for a character."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_needs_for_character(session, character_id)

    async def get_satisfying_location_for_need(self, *, need_kind: str) -> str | None:
        """Open a session and return a location id satisfying the need kind, or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_satisfying_location_for_need(session, need_kind)

    async def create_goal(
        self,
        *,
        character_id: str,
        description: str,
        urgency: int,
        game_time: TimePoint,
    ) -> str:
        """Open a session and create a Goal node, returning its id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await create_goal(
                session,
                character_id=character_id,
                description=description,
                urgency=urgency,
                game_time=game_time,
            )

    async def create_goal_targets_edge(
        self, *, goal_id: str, target_id: str, priority: int
    ) -> None:
        """Open a session and write a GOAL_TARGETS edge to a target location."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await create_goal_targets_edge(session, goal_id, target_id, priority)

    async def move_character(self, *, character_id: str, location_id: str) -> None:
        """Open a session and move a character's LOCATED_AT edge (planning override)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await update_character_location(
                session, character_id=character_id, location_id=location_id
            )
