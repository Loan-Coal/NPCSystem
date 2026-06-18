"""
Module: faction_service
Layer: graph
Purpose: Session-scoped service that composes faction mutation and query functions.
Does NOT: implement business logic or validate request payloads.
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.factions
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession, AsyncTransaction
from pydantic import BaseModel

from npc_engine.graph.transaction_coordinator import run_in_tx
from npc_engine.graph.faction_queries import (
    get_controlled_locations,
    get_faction,
    get_factions_for_character,
    get_members_of_faction,
    get_standing,
    list_factions,
    list_standings,
)
from npc_engine.graph.faction_writer import (
    add_member,
    remove_controls,
    remove_member,
    set_controls,
    set_standing,
    upsert_faction,
)


class FactionService:
    """Session-scoped service for faction CRUD and relationship management.

    Mutations open an explicit transaction so that Cypher errors roll back
    cleanly. Reads run directly on the session (auto-commit reads).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise the service with an injected Neo4j session.

        Args:
            session: Active Neo4j async session for the current request.
        """
        self._session = session

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def upsert_faction(self, faction: BaseModel) -> None:
        """Insert or update a Faction node idempotently.

        Args:
            faction: Pydantic model with an ``id`` field and serializable faction properties.
        """
        async def _work(tx: AsyncTransaction) -> None:
            await upsert_faction(tx, faction)

        await run_in_tx(self._session, _work)

    async def add_member(
        self,
        *,
        character_id: str,
        faction_id: str,
        role: str,
        status: str,
    ) -> None:
        """Create or update a MEMBER_OF edge from a Character to a Faction.

        Args:
            character_id: ID of the character node.
            faction_id: ID of the faction node.
            role: Membership role (leader | officer | member | recruit).
            status: Membership status (active | exiled | deceased).

        Raises:
            FactionMembershipError: If either node is not found.
        """
        async def _work(tx: AsyncTransaction) -> None:
            await add_member(tx, character_id=character_id, faction_id=faction_id, role=role, status=status)

        await run_in_tx(self._session, _work)

    async def remove_member(self, *, character_id: str, faction_id: str) -> None:
        """Delete a MEMBER_OF edge between a Character and a Faction.

        Args:
            character_id: ID of the character node.
            faction_id: ID of the faction node.

        Raises:
            FactionMembershipError: If no MEMBER_OF edge exists.
        """
        async def _work(tx: AsyncTransaction) -> None:
            await remove_member(tx, character_id=character_id, faction_id=faction_id)

        await run_in_tx(self._session, _work)

    async def set_standing(self, *, src_id: str, dst_id: str, standing: int) -> None:
        """Create or update a directed STANDS_WITH edge between two factions.

        Args:
            src_id: ID of the source faction.
            dst_id: ID of the destination faction.
            standing: Integer from -100 to 100.

        Raises:
            FactionNotFoundError: If either faction node does not exist.
        """
        async def _work(tx: AsyncTransaction) -> None:
            await set_standing(tx, src_id=src_id, dst_id=dst_id, standing=standing)

        await run_in_tx(self._session, _work)

    async def set_controls(self, *, faction_id: str, location_id: str) -> None:
        """Create a CONTROLS edge from a Faction to a Location.

        Args:
            faction_id: ID of the faction node.
            location_id: ID of the location node.

        Raises:
            FactionNotFoundError: If the faction or location node does not exist.
        """
        async def _work(tx: AsyncTransaction) -> None:
            await set_controls(tx, faction_id=faction_id, location_id=location_id)

        await run_in_tx(self._session, _work)

    async def remove_controls(self, *, faction_id: str, location_id: str) -> None:
        """Delete a CONTROLS edge from a Faction to a Location.

        Args:
            faction_id: ID of the faction node.
            location_id: ID of the location node.

        Raises:
            FactionNotFoundError: If no CONTROLS edge exists.
        """
        async def _work(tx: AsyncTransaction) -> None:
            await remove_controls(tx, faction_id=faction_id, location_id=location_id)

        await run_in_tx(self._session, _work)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_faction(self, faction_id: str) -> dict[str, Any] | None:
        """Fetch a Faction node by ID.

        Args:
            faction_id: ID of the faction node.

        Returns:
            Dict of faction properties, or None if not found.
        """
        return await get_faction(self._session, faction_id)

    async def list_factions(self, is_active: bool | None = None) -> list[dict[str, Any]]:
        """List all Faction nodes, optionally filtered by active status.

        Args:
            is_active: If provided, filters to only active or inactive factions.

        Returns:
            List of faction property dicts ordered by name.
        """
        return await list_factions(self._session, is_active=is_active)

    async def get_factions_for_character(self, character_id: str) -> list[dict[str, Any]]:
        """Fetch all active factions a character belongs to, with membership details.

        Args:
            character_id: ID of the character node.

        Returns:
            List of dicts with ``faction`` and ``membership`` keys.
        """
        return await get_factions_for_character(self._session, character_id)

    async def get_members_of_faction(self, faction_id: str) -> list[dict[str, Any]]:
        """Fetch all active characters belonging to a faction, with membership details.

        Args:
            faction_id: ID of the faction node.

        Returns:
            List of dicts with ``character`` and ``membership`` keys.
        """
        return await get_members_of_faction(self._session, faction_id)

    async def get_standing(self, src_id: str, dst_id: str) -> int | None:
        """Fetch the directed standing from one faction toward another.

        Args:
            src_id: ID of the source faction.
            dst_id: ID of the destination faction.

        Returns:
            Integer standing (-100 to 100), or None if no edge exists.
        """
        return await get_standing(self._session, src_id, dst_id)

    async def list_standings(self, faction_id: str) -> list[dict[str, Any]]:
        """Fetch all directed STANDS_WITH edges from a faction.

        Args:
            faction_id: ID of the source faction.

        Returns:
            List of dicts with ``target`` and ``standing`` keys, ordered by standing desc.
        """
        return await list_standings(self._session, faction_id)

    async def get_controlled_locations(self, faction_id: str) -> list[dict[str, Any]]:
        """Fetch all locations controlled by a faction.

        Args:
            faction_id: ID of the faction node.

        Returns:
            List of location property dicts, ordered by name.
        """
        return await get_controlled_locations(self._session, faction_id)
