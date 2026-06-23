"""
Module: interaction_repository
Layer: graph
Purpose: Neo4j adapter for the interaction graph domain. Opens a session per call from the
         injected GraphDB and delegates to quest_writer / quest_queries /
         quest_verification_queries, so the interaction quest handlers and verifiers depend
         on the InteractionGraphPort abstraction and hold no session for their reads.
         Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: mutate quest state, contain handler/verifier logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_interaction_graph_repo).
"""

from __future__ import annotations

from typing import Any
from npc_engine.graph.db import GraphDB
from npc_engine.graph.quest.quest_queries import get_active_quest_for_player
from npc_engine.graph.quest.quest_verification_queries import (
    count_player_co_located_with,
    count_player_has_item,
    count_player_located_at,
    count_player_was_at,
    count_target_inactive,
)
from npc_engine.graph.quest.quest_writer import get_quest_state


class Neo4jInteractionRepository:
    """Session-per-call Neo4j adapter for interaction reads (InteractionGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_quest_state(self, *, quest_id: str, player_id: str) -> dict[str, Any] | None:
        """Open a session and return the QuestState snapshot for (quest_id, player_id)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_quest_state(session=session, quest_id=quest_id, player_id=player_id)

    async def get_active_quest_for_player(self, *, player_id: str) -> dict[str, Any] | None:
        """Open a session and return the player's most recent active quest state."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_active_quest_for_player(session, player_id)

    async def count_player_has_item(self, *, player_id: str, item_id: str) -> int:
        """Open a session and count the player's owned quantity of item_id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await count_player_has_item(session, player_id=player_id, item_id=item_id)

    async def count_player_located_at(self, *, player_id: str, location_id: str) -> int:
        """Open a session and check whether the player is currently at the location."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await count_player_located_at(session, player_id=player_id, location_id=location_id)

    async def count_player_was_at(self, *, player_id: str, location_id: str) -> int:
        """Open a session and check whether the player has visited the location."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await count_player_was_at(session, player_id=player_id, location_id=location_id)

    async def count_target_inactive(self, *, target_id: str) -> int:
        """Open a session and check whether the target Character is inactive."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await count_target_inactive(session, target_id=target_id)

    async def count_player_co_located_with(self, *, player_id: str, target_id: str) -> int:
        """Open a session and check whether the player and target share a location."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await count_player_co_located_with(session, player_id=player_id, target_id=target_id)
