"""
Module: investigation_repository
Layer: graph
Purpose: Neo4j adapter for the investigation graph domain. Opens a session per call from
         the injected GraphDB and delegates to investigation_queries, so the
         InvestigationEngine depends on the InvestigationGraphPort abstraction and holds no
         session. Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: detect contradictions, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.progression.get_investigation_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.db import GraphDB
from npc_engine.graph.intrigue.investigation_queries import (
    get_alibi_window,
    get_contradicting_rumors,
    get_deductions_for_character,
    get_evidence_for_event,
    get_suspects_for_event,
    get_witnesses_of_event,
)


class Neo4jInvestigationRepository:
    """Session-per-call Neo4j adapter for investigation reads (InvestigationGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_evidence_for_event(self, *, event_id: str) -> list[dict[str, Any]]:
        """Open a session and return Evidence nodes linked to the event."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_evidence_for_event(session, event_id)

    async def get_witnesses_of_event(self, *, event_id: str) -> list[dict[str, Any]]:
        """Open a session and return WITNESSED edges for the event."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_witnesses_of_event(session, event_id)

    async def get_suspects_for_event(self, *, event_id: str) -> list[dict[str, Any]]:
        """Open a session and return SUSPECTS edges linked to the event."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_suspects_for_event(session, event_id)

    async def get_deductions_for_character(
        self, *, character_id: str
    ) -> list[dict[str, Any]]:
        """Open a session and return Deduction nodes held by the investigator."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_deductions_for_character(session, character_id)

    async def get_contradicting_rumors(self, *, event_id: str) -> list[dict[str, Any]]:
        """Open a session and return CONTRADICTS-linked Rumor pairs for the event."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_contradicting_rumors(session, event_id)

    async def get_alibi_window(
        self, *, character_id: str, from_tick: int, to_tick: int
    ) -> list[dict[str, Any]]:
        """Open a session and return the character's WAS_AT history in the tick window."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_alibi_window(
                session, character_id=character_id, from_tick=from_tick, to_tick=to_tick
            )
