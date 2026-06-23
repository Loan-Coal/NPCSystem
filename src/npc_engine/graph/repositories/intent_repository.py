"""
Module: intent_repository
Layer: graph
Purpose: Neo4j adapter for the intent graph domain. Opens a session per call from the
         injected GraphDB and delegates to intent_queries (trigger reads) and
         intent_queue_writer (PendingIntent queue writes), so the agenda intent engines
         depend on the IntentGraphPort abstraction and hold no session. Swap seam for
         cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: score intents, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_intent_formation_engine).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.intent.intent_queries import (
    get_npc_location,
    get_player_location,
    get_unmet_needs,
    get_unresolved_goals,
    get_witnessed_events,
)
from npc_engine.graph.intent.intent_queue_writer import enqueue_intent, expire_old_intents

if TYPE_CHECKING:
    from npc_engine.common.intent_models import ConversationIntent
    from npc_engine.config import Settings


class Neo4jIntentRepository:
    """Session-per-call Neo4j adapter for the intent domain (IntentGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_npc_location(self, *, npc_id: str) -> str | None:
        """Open a session and return the NPC's current location id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_npc_location(session, npc_id)

    async def get_player_location(self, *, player_id: str) -> str | None:
        """Open a session and return the player's current location id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_player_location(session, player_id)

    async def get_unmet_needs(self, *, npc_id: str) -> list[dict[str, Any]]:
        """Open a session and return the NPC's unmet Need nodes."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_unmet_needs(session, npc_id)

    async def get_witnessed_events(
        self, *, npc_id: str, since_tick: int
    ) -> list[dict[str, Any]]:
        """Open a session and return Event nodes learned at or after since_tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_witnessed_events(session, npc_id, since_tick)

    async def get_unresolved_goals(self, *, npc_id: str) -> list[dict[str, Any]]:
        """Open a session and return the NPC's unresolved Goal nodes."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_unresolved_goals(session, npc_id)

    async def enqueue_intent(
        self, intent: ConversationIntent, *, settings: Settings
    ) -> None:
        """Open a session and enqueue the scored intent (cap-enforced)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await enqueue_intent(session, intent, settings=settings)

    async def expire_old_intents(self, *, cutoff_tick: int) -> int:
        """Open a session and expire intents created before cutoff_tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await expire_old_intents(session, cutoff_tick=cutoff_tick)
