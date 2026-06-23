"""
Module: memory_consolidation_repository
Layer: graph
Purpose: Neo4j adapter for the memory-consolidation graph domain. Opens a session per
         operation from the injected GraphDB and delegates to graph.belief_queries,
         graph.memory_queries, graph.witnessed_queries, and graph.memory_service, so
         MemoryConsolidationEngine depends on the abstraction and holds no session.
         Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: summarise turns, call LLMs, contain engine logic, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.progression.get_memory_consolidation_engine).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from npc_engine.graph.knowledge.belief_queries import get_beliefs_for_character
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.memory.memory_queries import get_memories_for_character
from npc_engine.graph.memory.memory_service import create_memory
from npc_engine.graph.knowledge.witnessed_queries import get_undisclosed_witnesses

if TYPE_CHECKING:
    from npc_engine.world.time_utils import TimePoint


class Neo4jMemoryConsolidationRepository:
    """Session-per-call Neo4j adapter for memory consolidation (MemoryConsolidationGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_beliefs(self, *, character_id: str, k: int) -> list[dict[str, Any]]:
        """Open a session and return the character's top-k beliefs."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_beliefs_for_character(session, character_id=character_id, k=k)

    async def get_recent_memories(self, *, character_id: str, k: int) -> list[dict[str, Any]]:
        """Open a session and return the character's top-k recent memories."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_memories_for_character(session, character_id=character_id, k=k)

    async def get_undisclosed_witnesses(self, *, npc_id: str) -> list[dict[str, Any]]:
        """Open a session and return the NPC's undisclosed WITNESSED observations."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_undisclosed_witnesses(session, npc_id=npc_id)

    async def create_memory(
        self,
        *,
        character_id: str,
        content: str,
        vividness: int,
        emotional_charge: int,
        game_time: TimePoint,
    ) -> str:
        """Open a session and persist a consolidated Memory node; return its id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await create_memory(
                session,
                character_id=character_id,
                content=content,
                vividness=vividness,
                emotional_charge=emotional_charge,
                game_time=game_time,
            )
