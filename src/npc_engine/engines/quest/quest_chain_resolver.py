"""
Module: quest_chain_resolver
Layer: engines
Purpose: Resolves quest chain transitions — after a quest reaches a terminal outcome,
    queries UNLOCKS edges and calls offer_quest for each unlocked successor.
    Also supports choice-based branching (EXP-218): choose() selects the successor
    whose UNLOCKS.on_choice_id matches the player's choice_id.
Dependencies: npc_engine.engines.ports.quest_port, npc_engine.utils.logging (structured).
Used by: npc_engine.engines.quest.quest_lifecycle_engine (injected as optional param),
    npc_engine.api.routes.quest (POST /quest/{id}/choose)

Does NOT: call the LLM, generate quests, or modify graph state directly.
    Does NOT: hold a Neo4j session (DEC-122 / SEV-24).
Dependencies injected: offer_service (via __init__), chain_repo (via __init__).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from npc_engine.engines.ports.quest_port import QuestChainGraphPort


_logger = logging.getLogger(__name__)


class QuestOfferServiceProtocol(Protocol):
    """Minimal offer-service interface required by QuestChainResolver.

    Implementors must provide ``offer_quest`` with the simplified chain-offer
    signature. The full ``QuestOfferService`` is wrapped by a thin adapter in
    the composition root; for unit tests a mock suffices.
    """

    async def offer_quest(
        self,
        *,
        next_quest_id: str,
        player_id: str,
    ) -> dict:
        """Offer a quest to a player identified only by IDs.

        Args:
            next_quest_id: Quest node ID to offer.
            player_id: Player character ID.

        Returns:
            Persisted quest state payload dict with status ``"offered"``.
        """
        ...


class QuestChainResolver:
    """Resolves UNLOCKS chains after a quest reaches a terminal outcome.

    On ``resolve(quest_id, player_id, outcome)``:
    1. Calls ``chain_repo.get_unlocked_quests(quest_id=..., outcome=...)`` to find successors.
    2. For each successor, calls ``self._offer_service.offer_quest(next_quest_id=..., player_id=...)``.
    3. Logs each resolved chain transition with structured logging.

    If no UNLOCKS edges exist the method is a no-op.

    Attributes:
        _offer_service: Injected offer-service adapter (QuestOfferServiceProtocol).
        _chain_repo: Graph port for chain reads (QuestChainGraphPort).
    """

    def __init__(
        self,
        offer_service: QuestOfferServiceProtocol,
        chain_repo: QuestChainGraphPort,
    ) -> None:
        """Initialise the resolver with an injected offer-service and chain repo.

        Args:
            offer_service: Adapter implementing QuestOfferServiceProtocol.
                Injected by the composition root; never instantiated internally.
            chain_repo: QuestChainGraphPort — graph port for UNLOCKS queries.
        """
        self._offer_service = offer_service
        self._chain_repo = chain_repo

    async def resolve(
        self,
        *,
        quest_id: str,
        player_id: str,
        outcome: str,
    ) -> None:
        """Find and offer all quests unlocked by quest_id at the given outcome.

        Args:
            quest_id: Completed/failed quest node ID.
            player_id: Player character ID.
            outcome: Terminal outcome string — ``"complete"``, ``"fail"``, or ``"expire"``.

        Returns:
            None. Side-effect: offer_quest called for each unlocked successor.
        """
        next_quest_ids: list[str] = await self._chain_repo.get_unlocked_quests(
            quest_id=quest_id,
            outcome=outcome,
        )
        for next_quest_id in next_quest_ids:
            await self._offer_service.offer_quest(
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

    async def choose(
        self,
        *,
        quest_id: str,
        player_id: str,
        choice_id: str,
    ) -> str | None:
        """Select and offer the successor quest matching the player's choice.

        Queries for an UNLOCKS edge where ``on_choice_id == choice_id``. If found,
        calls ``offer_quest`` for the matched successor and returns its ID.
        If no edge matches (including when all UNLOCKS edges have null on_choice_id),
        returns None without calling offer_quest — preserving auto-unlock back-compat.

        Args:
            quest_id: The quest the player just made a choice in.
            player_id: Player character ID.
            choice_id: Identifier of the player's chosen option (capped upstream).

        Returns:
            The next quest ID that was offered, or None if no match.
        """
        next_quest_id: str | None = await self._chain_repo.get_choice_unlocked_quest(
            quest_id=quest_id,
            choice_id=choice_id,
        )
        if next_quest_id is None:
            _logger.info(
                "quest_choice_no_match",
                extra={"quest_id": quest_id, "choice_id": choice_id, "player_id": player_id},
            )
            return None
        return await self._offer_choice_successor(
            quest_id=quest_id, player_id=player_id,
            choice_id=choice_id, next_quest_id=next_quest_id,
        )

    async def _offer_choice_successor(
        self, *, quest_id: str, player_id: str, choice_id: str, next_quest_id: str,
    ) -> str:
        """Offer the chosen successor quest and log the resolution."""
        await self._offer_service.offer_quest(
            next_quest_id=next_quest_id, player_id=player_id,
        )
        _logger.info(
            "quest_choice_resolved",
            extra={"quest_id": quest_id, "choice_id": choice_id, "next_quest_id": next_quest_id, "player_id": player_id},
        )
        return next_quest_id
