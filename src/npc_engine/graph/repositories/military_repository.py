"""
Module: military_repository
Layer: graph
Purpose: Neo4j adapter for the military graph domain. Opens a session per operation
         from the injected GraphDB and delegates to graph.military_queries,
         graph.military_control_writer, and graph.military_writer, so the military
         services depend on the abstraction and hold no session. Swap seam for
         cache/alternate-DB/microservice backends (DEC-122 / SEV-24).
Does NOT: resolve battles, compute yields, call LLMs, contain engine logic, or import
          the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.politics.get_military_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.military.military_control_writer import (
    add_faction_treasury,
    remove_controls_location,
    set_controls_location,
    set_resource_depletion,
)
from npc_engine.graph.military.military_queries import (
    get_armies_in_conflict,
    get_army_at_location,
    get_faction_resource_nodes,
)
from npc_engine.graph.military.military_writer import emit_battle_event, set_army_strength


class Neo4jMilitaryRepository:
    """Session-per-call Neo4j adapter for the military domain (MilitaryGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_armies_in_conflict(self) -> list[dict[str, Any]]:
        """Open a session and return locations with armies from >=2 factions."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_armies_in_conflict(session)

    async def get_army_at_location(self, *, location_id: str) -> list[dict[str, Any]]:
        """Open a session and return all armies occupying a location."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_army_at_location(session, location_id)

    async def get_faction_resource_nodes(self) -> list[dict[str, Any]]:
        """Open a session and return non-depleted (faction, resource_node) pairs."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_faction_resource_nodes(session)

    async def set_army_strength(self, *, army_id: str, strength: int) -> None:
        """Open a session and update an army's strength."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await set_army_strength(session, army_id=army_id, strength=strength)

    async def set_controls_location(
        self,
        *,
        faction_id: str,
        location_id: str,
        control_strength: int,
        contested_by: str | None = None,
    ) -> None:
        """Open a session and upsert a CONTROLS edge."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await set_controls_location(
                session,
                faction_id=faction_id,
                location_id=location_id,
                control_strength=control_strength,
                contested_by=contested_by,
            )

    async def remove_controls_location(self, *, faction_id: str, location_id: str) -> None:
        """Open a session and delete a CONTROLS edge."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await remove_controls_location(
                session, faction_id=faction_id, location_id=location_id
            )

    async def emit_battle_event(
        self,
        *,
        event_id: str,
        summary: str,
        severity: int,
        location_id: str,
        occurred_at: str,
        tick_id: int,
        winner_faction_id: str,
    ) -> None:
        """Open a session and write a public battle Event node."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await emit_battle_event(
                session,
                event_id=event_id,
                summary=summary,
                severity=severity,
                location_id=location_id,
                occurred_at=occurred_at,
                tick_id=tick_id,
                winner_faction_id=winner_faction_id,
            )

    async def add_faction_treasury(self, *, faction_id: str, amount: int) -> None:
        """Open a session and adjust a faction's treasury."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await add_faction_treasury(session, faction_id=faction_id, amount=amount)

    async def set_resource_depletion(self, *, resource_node_id: str, depletion: int) -> None:
        """Open a session and set a ResourceNode's depletion level."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await set_resource_depletion(
                session, resource_node_id=resource_node_id, depletion=depletion
            )
