"""
Module: need_repository
Layer: graph
Purpose: Neo4j-backed implementation of the engine NeedGraphPort. Opens a session per
         operation from the injected GraphDB and delegates to need_queries/need_writer,
         so NeedDecayEngine depends on the abstraction and never holds a session. This
         is the swap seam: a cache, alternate DB, or graph-microservice client can
         replace this adapter behind the same structural Protocol (DEC-122 / SEV-24).
Does NOT: contain decay/business logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.social.get_need_decay_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.needs_goals.need_queries import get_all_needs_with_location
from npc_engine.graph.needs_goals.need_writer import set_need_level


class Neo4jNeedRepository:
    """Session-per-call Neo4j adapter for the engine NeedGraphPort.

    Holds the long-lived GraphDB driver holder and opens (and closes) one session per
    operation, so it is safe to construct once as a process singleton and inject into
    the singleton NeedDecayEngine.
    """

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_all_needs_with_location(self) -> list[dict[str, Any]]:
        """Open a session and return all Need rows joined with location + satisfier.

        Returns:
            List of need dicts (need_id, kind, level, decay_rate, character_id,
            location_id, satisfaction_magnitude).
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_all_needs_with_location(session)

    async def set_need_level(self, *, need_id: str, level: int) -> None:
        """Open a session and persist a Need node's new level.

        Args:
            need_id: ID of the Need node to update.
            level: New level (clamped to [0, 100] by the writer).
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await set_need_level(session, need_id=need_id, level=level)
