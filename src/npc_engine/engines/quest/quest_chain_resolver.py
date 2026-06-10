"""
Module: quest_chain_resolver
Layer: engines
Purpose: Resolves quest chain transitions — after a quest reaches a terminal outcome,
    queries UNLOCKS edges and calls offer_quest for each unlocked successor.
Dependencies: npc_engine.graph.quest_chain_queries, npc_engine.utils.logging (structured).
Used by: npc_engine.engines.quest.quest_lifecycle_engine (injected as optional param)

Does NOT: call the LLM, generate quests, or modify graph state directly.
Does NOT: wire into api/dependencies.py (slice-2 responsibility).
Dependencies injected: offer_service (via __init__); AsyncSession (per resolve call).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from neo4j import AsyncSession

from npc_engine.graph.quest_chain_queries import get_unlocked_quests


if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)


class QuestOfferServiceProtocol(Protocol):
    """Minimal offer-service interface required by QuestChainResolver.

    Implementors must provide ``offer_quest`` with the simplified chain-offer
    signature. The full ``QuestOfferService`` is wrapped by a thin adapter in
    slice-2; for unit tests a mock suffices.
    """

    async def offer_quest(
        self,
        *,
        session: AsyncSession,
        next_quest_id: str,
        player_id: str,
    ) -> dict:
        """Offer a quest to a player identified only by IDs.

        Args:
            session: Active Neo4j async session.
            next_quest_id: Quest node ID to offer.
            player_id: Player character ID.

        Returns:
            Persisted quest state payload dict with status ``"offered"``.
        """
        ...


class QuestChainResolver:
    """Resolves UNLOCKS chains after a quest reaches a terminal outcome.

    On ``resolve(session, quest_id, player_id, outcome)``:
    1. Calls ``get_unlocked_quests(session, quest_id, outcome)`` to find successors.
    2. For each successor, calls ``self._offer_service.offer_quest(session, next_quest_id, player_id)``.
    3. Logs each resolved chain transition with structured logging.

    If no UNLOCKS edges exist the method is a no-op.

    Attributes:
        _offer_service: Injected offer-service adapter (QuestOfferServiceProtocol).
    """

    def __init__(self, offer_service: QuestOfferServiceProtocol) -> None:
        """Initialise the resolver with an injected offer-service.

        Args:
            offer_service: Adapter implementing QuestOfferServiceProtocol.
                Injected by the composition root; never instantiated internally.
        """
        self._offer_service = offer_service

    async def resolve(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        outcome: str,
    ) -> None:
        """Find and offer all quests unlocked by quest_id at the given outcome.

        Args:
            session: Active Neo4j async session.
            quest_id: Completed/failed quest node ID.
            player_id: Player character ID.
            outcome: Terminal outcome string — ``"complete"``, ``"fail"``, or ``"expire"``.

        Returns:
            None. Side-effect: offer_quest called for each unlocked successor.
        """
        next_quest_ids = await get_unlocked_quests(
            session=session,
            quest_id=quest_id,
            outcome=outcome,
        )
        for next_quest_id in next_quest_ids:
            await self._offer_service.offer_quest(
                session=session,
                next_quest_id=next_quest_id,
                player_id=player_id,
            )
            _logger.info(
                "quest_chain_resolved",
                extra={
                    "quest_id": quest_id,
                    "next_quest_id": next_quest_id,
                    "outcome": outcome,
                    "player_id": player_id,
                },
            )
