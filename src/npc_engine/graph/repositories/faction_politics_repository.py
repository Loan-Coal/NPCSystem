"""
Module: faction_politics_repository
Layer: graph
Purpose: Neo4j adapter for the faction-politics graph domain. Opens a session per call
         from the injected GraphDB and delegates to faction_politics_queries (reads),
         faction_writer.set_standing (the STANDS_WITH write, run via run_in_tx), and
         faction_history_service.record_standing_change (the append-only history), so
         FactionPoliticsEngine depends on FactionPoliticsGraphPort and holds no session
         (DEC-122 / SEV-24).
Does NOT: apply rules, compute decay, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_faction_politics_engine).
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncTransaction

from npc_engine.graph.db import GraphDB
from npc_engine.graph.faction_history_service import record_standing_change
from npc_engine.graph.faction_politics_queries import (
    get_all_standings,
    get_character_factions,
    get_recent_events,
)
from npc_engine.graph.faction_writer import set_standing
from npc_engine.graph.transaction_coordinator import run_in_tx


class Neo4jFactionPoliticsRepository:
    """Session-per-call Neo4j adapter for the faction-politics domain (FactionPoliticsGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_recent_events(self) -> list[dict[str, str]]:
        """Open a session and return recent events with a src_character_id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_recent_events(session)

    async def get_character_factions(self, *, character_id: str) -> list[str]:
        """Open a session and return the character's active faction ids."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_character_factions(session, character_id=character_id)

    async def get_all_standings(self) -> list[dict[str, Any]]:
        """Open a session and return all STANDS_WITH edges."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_all_standings(session)

    async def commit_standing_change(
        self,
        *,
        src_id: str,
        dst_id: str,
        new_standing: int,
        delta: int,
        tick: int,
        cause_event_id: str | None = None,
        cause_rule_id: str | None = None,
    ) -> None:
        """Write the STANDS_WITH standing (in a tx) then append its FactionStandingEvent."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:

            async def _work(tx: AsyncTransaction) -> None:
                await set_standing(tx, src_id=src_id, dst_id=dst_id, standing=new_standing)

            await run_in_tx(session, _work)
            await record_standing_change(
                session,
                src_faction_id=src_id,
                dst_faction_id=dst_id,
                delta=delta,
                new_standing=new_standing,
                tick=tick,
                cause_event_id=cause_event_id,
                cause_rule_id=cause_rule_id,
            )
