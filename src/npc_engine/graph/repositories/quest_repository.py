"""
Module: quest_repository
Layer: graph
Purpose: Neo4j adapters for quest lifecycle, offer, and chain domains. Opens a session per
         operation from the injected GraphDB; atomic operations use run_in_tx internally.
         Implements QuestLifecycleGraphPort, QuestOfferGraphPort, and QuestChainGraphPort
         structurally (no import of engine Protocols — keeps graph free of engine deps).
Does NOT: contain engine logic, validate business rules beyond basic DB constraints,
          call LLMs, or import from engines/.
Dependencies injected: GraphDB.
Used by: api composition root (dependencies_engines.py).
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncTransaction

from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.event.event_writer import upsert_quest_lifecycle_event
from npc_engine.graph.quest.quest_chain_queries import (
    get_choice_unlocked_quest,
    get_unlocked_quests,
)
from npc_engine.graph.quest.quest_node_service import get_quest
from npc_engine.graph.quest.quest_writer import (
    create_quest_state_if_absent,
    get_quest_state,
    update_quest_node_status,
    upsert_quest_state,
)
from npc_engine.graph.infra.transaction_coordinator import run_in_tx
from npc_engine.graph.world_state.world_state_reader import get_world_state
from npc_engine.utils.errors import QuestTransitionError
from npc_engine.world.world_state import WorldState


class Neo4jQuestLifecycleRepository:
    """Session-per-call Neo4j adapter for the quest lifecycle domain (QuestLifecycleGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_quest_state(self, *, quest_id: str, player_id: str) -> dict[str, Any] | None:
        """Return the persisted QuestState dict[str, Any] or None if absent."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_quest_state(session=session, quest_id=quest_id, player_id=player_id)

    async def persist_state_and_event(
        self,
        *,
        quest_id: str,
        player_id: str,
        state_payload: dict[str, Any],
        event_node: Any,
    ) -> dict[str, Any]:
        """Atomically upsert quest state and emit a lifecycle event; return stored state."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            async def _work(tx: AsyncTransaction) -> dict[str, Any]:
                stored = await upsert_quest_state(
                    session=tx,
                    quest_id=quest_id,
                    player_id=player_id,
                    state_payload=state_payload,
                )
                await upsert_quest_lifecycle_event(tx=tx, event=event_node)
                return stored

            return await run_in_tx(session, _work)

    async def emit_lifecycle_event(self, *, event_node: Any) -> None:
        """Atomically write one quest lifecycle event node."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            async def _work(tx: AsyncTransaction) -> None:
                await upsert_quest_lifecycle_event(tx=tx, event=event_node)

            await run_in_tx(session, _work)

    async def update_quest_node_status(self, *, quest_id: str, status: str) -> None:
        """Update the Quest node's status field (non-atomic, called after persist)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await update_quest_node_status(session=session, quest_id=quest_id, status=status)

    async def get_world_state(self, *, world_id: str = "world") -> WorldState:
        """Return the singleton WorldState (used for commitment-memory TimePoint)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_world_state(session=session, world_id=world_id)


class Neo4jQuestOfferRepository:
    """Session-per-call Neo4j adapter for the quest offer domain (QuestOfferGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_quest(self, *, quest_id: str) -> dict[str, Any] | None:
        """Return the Quest node dict[str, Any] or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_quest(session, quest_id)

    async def update_quest_node_status(self, *, quest_id: str, status: str) -> None:
        """Update the Quest node's status field."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await update_quest_node_status(session=session, quest_id=quest_id, status=status)

    async def offer_quest_atomic(
        self,
        *,
        quest_id: str,
        player_id: str,
        state_payload: dict[str, Any],
        event_node: Any,
    ) -> dict[str, Any]:
        """Atomically create-if-absent QuestState and emit offered event; return stored state.

        Validates that the created/retrieved state is in offered status and that the
        reward_source_id is trusted. Raises QuestTransitionError on constraint violations
        so the transition aborts atomically.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            async def _work(tx: AsyncTransaction) -> dict[str, Any]:
                stored = await create_quest_state_if_absent(
                    session=tx,
                    quest_id=quest_id,
                    player_id=player_id,
                    state_payload=state_payload,
                )
                if stored.get("status") != "offered":
                    raise QuestTransitionError(
                        code="QUEST_TRANSITION_INVALID",
                        detail=f"Quest cannot be re-offered from status={stored.get('status')}",
                    )
                await upsert_quest_lifecycle_event(tx=tx, event=event_node)
                return stored

            return await run_in_tx(session, _work)


class Neo4jQuestChainRepository:
    """Session-per-call Neo4j adapter for the quest chain domain (QuestChainGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_quest(self, *, quest_id: str) -> dict[str, Any] | None:
        """Return the Quest node dict[str, Any] or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_quest(session, quest_id)

    async def get_unlocked_quests(self, *, quest_id: str, outcome: str) -> list[str]:
        """Return IDs of quests unlocked by quest_id at the given outcome."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_unlocked_quests(session=session, quest_id=quest_id, outcome=outcome)

    async def get_choice_unlocked_quest(
        self, *, quest_id: str, choice_id: str
    ) -> str | None:
        """Return the quest ID unlocked by a specific player choice, or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_choice_unlocked_quest(
                session=session, quest_id=quest_id, choice_id=choice_id
            )
