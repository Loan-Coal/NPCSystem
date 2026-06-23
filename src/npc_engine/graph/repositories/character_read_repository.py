"""
Module: character_read_repository
Layer: graph
Purpose: Neo4j adapter for the shared character-read domain. Opens a session per call from
         the injected GraphDB and delegates to character_reader.get_npc_ids, so engines
         depend on the CharacterReadPort abstraction and hold no session.
         Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: write characters, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (engines reading the active NPC roster).
"""

from __future__ import annotations

from npc_engine.graph.character.character_reader import get_npc_ids as get_npc_ids_query
from npc_engine.graph.db import GraphDB


class Neo4jCharacterReadRepository:
    """Session-per-call Neo4j adapter for character reads (CharacterReadPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_npc_ids(self) -> list[str]:
        """Open a session and return the IDs of all active non-player Characters."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_npc_ids_query(session)
