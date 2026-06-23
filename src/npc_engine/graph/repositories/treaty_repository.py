"""
Module: treaty_repository
Layer: graph
Purpose: Neo4j adapter for the treaty graph domain. Opens a session per operation from
         the injected GraphDB and delegates to treaty_queries/treaty_service, so
         TreatyEngine depends on the abstraction and holds no session. Swap seam for
         cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: evaluate treaties, contain engine logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.politics.get_treaty_engine).
"""

from __future__ import annotations

from npc_engine.graph.db import GraphDB
from npc_engine.graph.political.treaty_queries import get_all_active_treaty_ids
from npc_engine.graph.political.treaty_service import (
    check_treaty_conditions_mechanical,
    expire_treaty,
    get_expiring_treaties_svc,
)


class Neo4jTreatyRepository:
    """Session-per-call Neo4j adapter for the treaty domain (TreatyGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_expiring_treaties(self, *, tick_id: int) -> list[str]:
        """Open a session and return ids of treaties at/past their expiry tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_expiring_treaties_svc(session, tick_id=tick_id)

    async def expire_treaty(self, *, treaty_id: str, tick_id: int) -> None:
        """Open a session and mark a treaty expired at the given tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await expire_treaty(session, treaty_id, tick_id)

    async def get_all_active_treaty_ids(self) -> list[str]:
        """Open a session and return ids of all active treaties."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_all_active_treaty_ids(session)

    async def check_treaty_conditions_mechanical(
        self, *, treaty_id: str, tick_id: int
    ) -> list[str]:
        """Open a session and return mechanically-violated condition descriptions."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await check_treaty_conditions_mechanical(session, treaty_id, tick_id)
