"""
Module: economy_repository
Layer: graph
Purpose: Neo4j adapter for the economy graph domain. Opens a session per call from the
         injected GraphDB and delegates to pricing_queries / item_writer / currency_writer,
         so the trade engine depends on the EconomyGraphPort abstraction and holds no
         session. Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: compute fair prices, contain engine logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_trade_engine).
"""

from __future__ import annotations

from npc_engine.graph.economy.currency_writer import transfer_currency_atomic
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.economy.item_writer import transfer_item_atomic
from npc_engine.graph.economy.pricing_queries import (
    check_faction_membership,
    get_active_event_types_at_location,
    get_character_location_id,
    get_character_location_type,
)


class Neo4jEconomyRepository:
    """Session-per-call Neo4j adapter for the economy domain (EconomyGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_character_location_type(self, *, character_id: str) -> str | None:
        """Open a session and return the character's location TYPE, or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_character_location_type(session, character_id)

    async def get_character_location_id(self, *, character_id: str) -> str | None:
        """Open a session and return the character's location id, or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_character_location_id(session, character_id)

    async def get_active_event_types_at_location(
        self, *, location_id: str, since_tick: int
    ) -> list[str]:
        """Open a session and return active event types at a location since a tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_active_event_types_at_location(session, location_id, since_tick)

    async def check_faction_membership(self, *, buyer_id: str, seller_id: str) -> bool:
        """Open a session and return whether buyer and seller share a faction."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await check_faction_membership(session, buyer_id, seller_id)

    async def transfer_item_atomic(
        self,
        *,
        source_id: str,
        destination_id: str,
        item_id: str,
        quantity: int,
        reason: str,
        request_id: str,
        idempotency_key: str,
        transfer_kind: str,
    ) -> None:
        """Open a session and transfer an item atomically."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await transfer_item_atomic(
                session,
                source_id=source_id,
                destination_id=destination_id,
                item_id=item_id,
                quantity=quantity,
                reason=reason,
                request_id=request_id,
                idempotency_key=idempotency_key,
                transfer_kind=transfer_kind,
            )

    async def transfer_currency_atomic(
        self,
        *,
        source_id: str,
        destination_id: str,
        amount: int,
        reason: str,
        request_id: str,
        idempotency_key: str,
        session_scope: str,
        transfer_kind: str,
    ) -> None:
        """Open a session and transfer currency atomically."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await transfer_currency_atomic(
                session,
                source_id=source_id,
                destination_id=destination_id,
                amount=amount,
                reason=reason,
                request_id=request_id,
                idempotency_key=idempotency_key,
                session_scope=session_scope,
                transfer_kind=transfer_kind,
            )
