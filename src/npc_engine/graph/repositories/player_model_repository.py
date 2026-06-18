"""
Module: player_model_repository
Layer: graph
Purpose: Neo4j adapter for the player-model write domain. Opens a session per call from the
         injected GraphDB and delegates to player_model_writer.upsert_player_model, so the
         player-model tick depends on the PlayerModelGraphPort abstraction and holds no
         session. Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: derive perceived trust/intent, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_player_model_tick).
"""

from __future__ import annotations

from npc_engine.graph.db import GraphDB
from npc_engine.graph.player_model_writer import upsert_player_model


class Neo4jPlayerModelRepository:
    """Session-per-call Neo4j adapter for the player-model write (PlayerModelGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def upsert_player_model(
        self,
        *,
        npc_id: str,
        player_id: str,
        perceived_trust: int,
        perceived_intent: str,
        tick: int,
    ) -> None:
        """Open a session and upsert the NPC's PlayerModel node (idempotent MERGE)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await upsert_player_model(
                session=session,
                npc_id=npc_id,
                player_id=player_id,
                perceived_trust=perceived_trust,
                perceived_intent=perceived_intent,
                tick=tick,
            )
