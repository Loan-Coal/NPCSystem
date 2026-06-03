"""
Module: reputation_service
Layer: graph
Purpose: Session-scoped service that composes reputation mutation and query functions.
Does NOT: implement business logic or validate request payloads.
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.reputation
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

from npc_engine.graph.reputation_queries import (
    get_reputation,
    get_reputation_context_for_npc,
    list_reputations,
)
from npc_engine.graph.reputation_event_seeder import (
    create_reputation_event,
    seed_reputation_awareness,
)
from npc_engine.graph.reputation_writer import (
    adjust_reputation,
    adjust_reputation_for_event,
    set_reputation,
)


class ReputationService:
    """Session-scoped service for reputation CRUD operations.

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

    async def set_reputation(self, *, character_id: str, faction_id: str, standing: int) -> None:
        """Create or update a HAS_REPUTATION_WITH edge with a clamped standing value.

        Args:
            character_id: ID of the character node.
            faction_id: ID of the faction node.
            standing: Desired standing; clamped to [-100, 100] before write.

        Raises:
            ReputationNotFoundError: If the character or faction node does not exist.
        """
        tx = await self._session.begin_transaction()
        async with tx:
            await set_reputation(tx, character_id=character_id, faction_id=faction_id, standing=standing)

    async def adjust_reputation(self, *, character_id: str, faction_id: str, delta: int) -> int:
        """Apply a delta to a character's standing with a faction, clamped to [-100, 100].

        Args:
            character_id: ID of the character node.
            faction_id: ID of the faction node.
            delta: Integer change to apply.

        Returns:
            The new clamped standing value.

        Raises:
            ReputationNotFoundError: If the character or faction node does not exist.
        """
        tx = await self._session.begin_transaction()
        async with tx:
            return cast(int, await adjust_reputation(tx, character_id=character_id, faction_id=faction_id, delta=delta))

    async def adjust_reputation_with_event(
        self,
        *,
        character_id: str,
        faction_id: str,
        delta: int,
        location_id: str,
        tick_id: int,
    ) -> int:
        """Adjust a character's reputation and seed a gossip-propagatable Event.

        Runs all three writes in a single transaction:
        1. Adjust the HAS_REPUTATION_WITH standing.
        2. Create a reputation_change Event node at location_id.
        3. Seed KNOWS_ABOUT edges for active NPCs at location_id.

        The gossip tick can then propagate the event to NPCs at other locations.

        Args:
            character_id: ID of the character node.
            faction_id: ID of the faction node.
            delta: Integer standing delta.
            location_id: Location where the standing change occurred.
            tick_id: Current game tick.

        Returns:
            The new clamped standing value.

        Raises:
            ReputationNotFoundError: If character or faction node is absent.
        """
        tx = await self._session.begin_transaction()
        async with tx:
            new_standing = await adjust_reputation(
                tx, character_id=character_id, faction_id=faction_id, delta=delta
            )
            event_id = await create_reputation_event(
                tx,
                character_id=character_id,
                faction_id=faction_id,
                delta=delta,
                location_id=location_id,
                tick_id=tick_id,
            )
            await seed_reputation_awareness(
                tx,
                event_id=event_id,
                location_id=location_id,
                tick_id=tick_id,
            )
        return new_standing

    async def adjust_reputation_for_event(
        self, *, character_id: str, faction_id: str, delta: int
    ) -> None:
        """Apply a reputation delta triggered by an in-game event.

        Args:
            character_id: ID of the character node.
            faction_id: ID of the faction node.
            delta: Integer change to apply.

        Raises:
            ReputationNotFoundError: If the character or faction node does not exist.
        """
        tx = await self._session.begin_transaction()
        async with tx:
            await adjust_reputation_for_event(
                tx, character_id=character_id, faction_id=faction_id, delta=delta
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_reputation(self, *, character_id: str, faction_id: str) -> dict[str, Any] | None:
        """Fetch a single HAS_REPUTATION_WITH edge.

        Args:
            character_id: ID of the character node.
            faction_id: ID of the faction node.

        Returns:
            Dict with faction_id, faction_name, and standing, or None if absent.
        """
        return cast(
            dict[str, Any] | None,
            await get_reputation(self._session, character_id=character_id, faction_id=faction_id),
        )

    async def list_reputations(self, *, character_id: str) -> list[dict[str, Any]]:
        """Fetch all HAS_REPUTATION_WITH edges for a character.

        Args:
            character_id: ID of the character node.

        Returns:
            List of dicts with faction_id, faction_name, and standing.
        """
        return cast(
            list[dict[str, Any]],
            await list_reputations(self._session, character_id=character_id),
        )

    async def get_reputation_context_for_npc(
        self, *, npc_id: str, player_id: str, threshold: int
    ) -> list[dict[str, Any]]:
        """Fetch player reputation lines relevant to the NPC's faction memberships.

        Args:
            npc_id: ID of the NPC character node.
            player_id: ID of the player character node.
            threshold: Minimum absolute standing value to include.

        Returns:
            List of dicts with faction_name, standing, and label.
        """
        return cast(
            list[dict[str, Any]],
            await get_reputation_context_for_npc(
                self._session, npc_id=npc_id, player_id=player_id, threshold=threshold
            ),
        )
