"""
Module: player_location_read_repository
Layer: graph
Purpose: Neo4j adapter for the shared player-location read domain. Opens a session per
         call from the injected GraphDB and delegates to PlayerLocationReader, so engines
         depend on the PlayerLocationReadPort abstraction and hold no session.
         Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: move NPCs, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (engines reading player/NPC co-location state).
"""

from __future__ import annotations

from npc_engine.graph.db import GraphDB
from npc_engine.graph.player_location_reader import PlayerLocationReader


class Neo4jPlayerLocationReadRepository:
    """Session-per-call Neo4j adapter for player-location reads (PlayerLocationReadPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder and a stateless reader.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db
        self._reader = PlayerLocationReader()

    async def get_collocated_pairs(self) -> list[tuple[str, str]]:
        """Open a session and return all (npc_id, player_id) co-located pairs."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await self._reader.get_collocated_pairs(session)

    async def get_player_idle_ticks(
        self, *, npc_id: str, player_id: str, tick_id: int
    ) -> int:
        """Open a session and return the player's idle-tick count at the NPC's location."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await self._reader.get_player_idle_ticks(
                session, npc_id=npc_id, player_id=player_id, tick_id=tick_id
            )
