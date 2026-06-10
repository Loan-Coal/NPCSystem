"""
Module: quest_chain_offer_adapter
Layer: engines
Purpose: Adapts QuestOfferService to the minimal QuestOfferServiceProtocol required
         by QuestChainResolver — resolves quest metadata from the graph and synthesises
         a system-level QuestTransitionMeta for chain-triggered offers.
Dependencies: npc_engine.engines.quest.quest_offer_service,
              npc_engine.engines.quest.models,
              npc_engine.graph.quest_node_service (via injected fn),
              npc_engine.utils.errors.
Used by: npc_engine.api.dependencies_engines (injected into QuestChainResolver).

Does NOT: call LLMs, implement state machine transitions, or open transactions directly.
Dependencies injected: offer_service (via __init__); get_quest_fn (via __init__, default
                       is graph.quest_node_service.get_quest).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from neo4j import AsyncSession

from npc_engine.engines.quest.models import QuestTransitionMeta
from npc_engine.engines.quest.quest_offer_service import QuestOfferService
from npc_engine.utils.errors import QuestTransitionError

_CHAIN_ACTOR_ID = "chain_resolver"
_CHAIN_REASON = "quest_chain_unlock"
_CHAIN_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _make_chain_meta(quest_id: str, player_id: str) -> QuestTransitionMeta:
    idempotency_key = f"chain:{quest_id}:{player_id}"
    return QuestTransitionMeta(
        request_id=str(uuid.uuid5(_CHAIN_NAMESPACE, idempotency_key)),
        actor_id=_CHAIN_ACTOR_ID,
        reason=_CHAIN_REASON,
        idempotency_key=idempotency_key,
        idempotency_request_hash=str(uuid.uuid5(_CHAIN_NAMESPACE, idempotency_key)),
    )


class QuestChainOfferAdapter:
    """Bridges QuestOfferService to the minimal QuestOfferServiceProtocol.

    On ``offer_quest(session, next_quest_id, player_id)``:
    1. Fetches the Quest node via ``get_quest_fn`` to read the description as title.
    2. Synthesises a system QuestTransitionMeta with a deterministic idempotency key.
    3. Calls ``offer_service.offer_quest`` with empty objectives and no rewards.

    Chain-offered quests start with no specific objectives — the designer provides
    objective data separately if needed.

    Attributes:
        _offer_service: Injected QuestOfferService.
        _get_quest: Async callable returning the Quest node dict or None.
    """

    def __init__(
        self,
        offer_service: QuestOfferService,
        get_quest_fn: Callable[[AsyncSession, str], Awaitable[dict[str, Any] | None]] | None = None,
    ) -> None:
        """Initialise the adapter.

        Args:
            offer_service: QuestOfferService singleton (injected by composition root).
            get_quest_fn: Async callable ``(session, quest_id) -> dict | None``; defaults
                to ``graph.quest_node_service.get_quest`` when None.
        """
        self._offer_service = offer_service
        if get_quest_fn is None:
            from npc_engine.graph.quest_node_service import get_quest
            self._get_quest: Callable[[AsyncSession, str], Awaitable[dict[str, Any] | None]] = get_quest
        else:
            self._get_quest = get_quest_fn

    async def offer_quest(
        self,
        *,
        session: AsyncSession,
        next_quest_id: str,
        player_id: str,
    ) -> dict:
        """Offer a chain-unlocked quest to a player.

        Args:
            session: Active Neo4j async session.
            next_quest_id: ID of the quest to offer.
            player_id: Player character ID.

        Returns:
            Persisted quest state payload dict with status ``"offered"``.

        Raises:
            QuestTransitionError: If the Quest node does not exist.
        """
        quest_node = await self._get_quest(session, next_quest_id)
        if quest_node is None:
            raise QuestTransitionError(
                code="QUEST_NOT_FOUND",
                detail=f"Chain-unlock target not found: quest_id={next_quest_id}",
            )
        title: str = quest_node.get("description") or next_quest_id
        meta = _make_chain_meta(quest_id=next_quest_id, player_id=player_id)
        return await self._offer_service.offer_quest(
            session=session,
            quest_id=next_quest_id,
            player_id=player_id,
            title=title,
            objectives=[],
            item_rewards=[],
            currency_reward=None,
            meta=meta,
        )
