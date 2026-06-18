"""
Module: world_state_repository
Layer: graph
Purpose: Neo4j adapter for the shared world-state graph domain. Opens a session per
         operation from the injected GraphDB and delegates to world_state_reader /
         world_state_writer, so engines depend on the abstraction and hold no session.
         Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: derive pacing/multipliers, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (engines that read/write world state).
"""

from __future__ import annotations

from npc_engine.graph.db import GraphDB
from npc_engine.graph.world_state_reader import get_world_state
from npc_engine.graph.world_state_writer import upsert_world_state
from npc_engine.world.world_state import WorldState


class Neo4jWorldStateRepository:
    """Session-per-call Neo4j adapter for the world-state domain (WorldStateGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_world_state(self, *, world_id: str = "world") -> WorldState:
        """Open a session and return the singleton WorldState (or a default model)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_world_state(session, world_id=world_id)

    async def upsert_world_state(self, *, world_state: WorldState) -> WorldState:
        """Open a session and upsert the singleton WorldState, returning the confirmed model."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await upsert_world_state(session, world_state)
