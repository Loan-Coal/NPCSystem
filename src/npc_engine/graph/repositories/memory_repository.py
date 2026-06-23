"""
Module: memory_repository
Layer: graph
Purpose: Neo4j adapter for the memory domain. Opens a session per call from the injected
         GraphDB and delegates to memory_service (create_memory + the two vividness decays),
         so MemoryEngine depends on the MemoryGraphPort abstraction and holds no session.
         Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: decide memory thresholds, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_memory_engine).
"""

from __future__ import annotations

from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.memory.memory_service import (
    create_memory,
    decay_all_vividness,
    decay_all_vividness_weighted,
)
from npc_engine.world.time_utils import TimePoint


class Neo4jMemoryRepository:
    """Session-per-call Neo4j adapter for memory writes/decay (MemoryGraphPort).

    Holds the long-lived GraphDB driver holder and opens one session per operation, so it
    is safe to construct once as a process singleton and inject into the singleton
    MemoryEngine.
    """

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def create_memory(
        self,
        *,
        character_id: str,
        content: str,
        vividness: int,
        emotional_charge: int,
        game_time: TimePoint,
        subject_player_id: str | None = None,
        kind: str | None = None,
    ) -> str:
        """Open a session and create a Memory node, returning its node id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await create_memory(
                session,
                character_id=character_id,
                content=content,
                vividness=vividness,
                emotional_charge=emotional_charge,
                game_time=game_time,
                subject_player_id=subject_player_id,
                kind=kind,
            )

    async def decay_all_vividness(self) -> int:
        """Open a session and reduce all Memory vividness by the default daily amount."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await decay_all_vividness(session)

    async def decay_all_vividness_weighted(
        self,
        *,
        base_decay: int,
        charge_divisor: int,
    ) -> int:
        """Open a session and apply charge-weighted vividness decay."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await decay_all_vividness_weighted(
                session,
                base_decay=base_decay,
                charge_divisor=charge_divisor,
            )
