"""
Module: proactive_memory_read_repository
Layer: graph
Purpose: Neo4j adapter for the proactive-dialogue memory read domain. Opens a session per
         call from the injected GraphDB and delegates to ProactiveMemoryReader, so the
         ProactiveDialogueEngine depends on the ProactiveMemoryReadPort abstraction and
         holds no session. Swap seam for cache/alternate DB backends (DEC-122 / SEV-24).
Does NOT: score triggers, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_proactive_dialogue_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.db import GraphDB
from npc_engine.graph.memory.proactive_memory_reader import ProactiveMemoryReader


class Neo4jProactiveMemoryReadRepository:
    """Session-per-call Neo4j adapter for proactive memory reads (ProactiveMemoryReadPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder and a stateless reader.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db
        self._reader = ProactiveMemoryReader()

    async def get_unshared_memories(
        self, *, npc_id: str, k: int = 10
    ) -> list[dict[str, Any]]:
        """Open a session and return up to k unshared memories ordered by vividness."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await self._reader.get_unshared_memories(session, npc_id=npc_id, k=k)
