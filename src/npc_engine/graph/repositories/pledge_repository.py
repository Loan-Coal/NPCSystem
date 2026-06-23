"""
Module: pledge_repository
Layer: graph
Purpose: Neo4j adapter for the pledge graph domain. Opens a session per operation from
         the injected GraphDB and delegates to pledge_service/pledge_violation_service,
         so OathEngine depends on the abstraction and holds no session. Swap seam for
         cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: emit events, contain engine logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.politics.get_oath_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.db import GraphDB
from npc_engine.graph.political.pledge_service import (
    break_pledge,
    get_all_active_pledgers_svc,
    get_expiring_pledges_svc,
)
from npc_engine.graph.political.pledge_violation_service import check_pledge_violations


class Neo4jPledgeRepository:
    """Session-per-call Neo4j adapter for the pledge domain (PledgeGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_expiring_pledges(self, *, tick_id: int) -> list[dict[str, Any]]:
        """Open a session and return pledges at/past their expiry tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_expiring_pledges_svc(session, tick_id=tick_id)

    async def break_pledge(
        self, *, pledger_id: str, pledgee_id: str, pledge_type: str, tick: int
    ) -> None:
        """Open a session and break a pledge between two characters."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await break_pledge(
                session,
                pledger_id=pledger_id,
                pledgee_id=pledgee_id,
                pledge_type=pledge_type,
                tick=tick,
            )

    async def get_all_active_pledgers(self) -> list[str]:
        """Open a session and return ids of all characters with an active pledge."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_all_active_pledgers_svc(session)

    async def check_pledge_violations(self, *, pledger_id: str, tick: int) -> list[dict[str, Any]]:
        """Open a session and return detected pledge violations for a pledger."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await check_pledge_violations(session, pledger_id=pledger_id, tick=tick)
