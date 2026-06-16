"""
Module: economy_port
Layer: engines
Purpose: Structural Protocol for the economy graph domain (pricing-context reads +
         atomic item/currency transfers) so the trade engine depends on one abstraction
         and holds no Neo4j session (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, compute fair prices, or import graph functions.
Dependencies injected: none (pure interface).
Used by: engines/economy/trade_engine; implemented structurally by
         npc_engine.graph.repositories.economy_repository.Neo4jEconomyRepository.
"""

from __future__ import annotations

from typing import Protocol


class EconomyGraphPort(Protocol):
    """Reads for pricing context and writes for atomic item/currency transfers."""

    async def get_character_location_type(self, *, character_id: str) -> str | None:
        """Return the location TYPE the character is at, or None."""
        ...

    async def get_character_location_id(self, *, character_id: str) -> str | None:
        """Return the location id the character is at, or None."""
        ...

    async def get_active_event_types_at_location(
        self, *, location_id: str, since_tick: int
    ) -> list[str]:
        """Return active event types at a location since the given tick."""
        ...

    async def check_faction_membership(self, *, buyer_id: str, seller_id: str) -> bool:
        """Return True when buyer and seller share a faction."""
        ...

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
        """Transfer an item atomically from source to destination."""
        ...

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
        """Transfer currency atomically from source to destination."""
        ...
