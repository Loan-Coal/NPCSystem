"""
Module: quest_chain_offer_adapter
Layer: engines
Purpose: Adapts QuestOfferService to the minimal QuestOfferServiceProtocol required
         by QuestChainResolver — resolves quest metadata from the graph and synthesises
         a system-level QuestTransitionMeta for chain-triggered offers.
Dependencies: npc_engine.engines.quest.quest_offer_service,
              npc_engine.engines.quest.models,
              npc_engine.engines.ports.quest_port (QuestChainGraphPort),
              npc_engine.utils.errors.
Used by: npc_engine.api.dependencies_engines (injected into QuestChainResolver).

Does NOT: call LLMs, implement state machine transitions, or hold a Neo4j session (DEC-122).
Dependencies injected: offer_service (via __init__), chain_repo (via __init__).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from npc_engine.engines.quest.models import QuestTransitionMeta
from npc_engine.engines.quest.quest_offer_service import QuestOfferService
from npc_engine.utils.errors import QuestTransitionError

if TYPE_CHECKING:
    from npc_engine.engines.ports.quest_port import QuestChainGraphPort

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

    On ``offer_quest(next_quest_id, player_id)``:
    1. Fetches the Quest node via ``chain_repo.get_quest`` to read the description as title.
    2. Synthesises a system QuestTransitionMeta with a deterministic idempotency key.
    3. Calls ``offer_service.offer_quest`` with empty objectives and no rewards.

    Chain-offered quests start with no specific objectives — the designer provides
    objective data separately if needed.

    Attributes:
        _offer_service: Injected QuestOfferService.
        _chain_repo: Injected QuestChainGraphPort for quest node reads.
    """

    def __init__(
        self,
        offer_service: QuestOfferService,
        chain_repo: QuestChainGraphPort,
    ) -> None:
        """Initialise the adapter.

        Args:
            offer_service: QuestOfferService singleton (injected by composition root).
            chain_repo: QuestChainGraphPort — provides get_quest() for title resolution.
        """
        self._offer_service = offer_service
        self._chain_repo = chain_repo

    async def offer_quest(
        self,
        *,
        next_quest_id: str,
        player_id: str,
    ) -> dict:
        """Offer a chain-unlocked quest to a player.

        Args:
            next_quest_id: ID of the quest to offer.
            player_id: Player character ID.

        Returns:
            Persisted quest state payload dict with status ``"offered"``.

        Raises:
            QuestTransitionError: If the Quest node does not exist.
        """
        quest_node = await self._chain_repo.get_quest(quest_id=next_quest_id)
        if quest_node is None:
            raise QuestTransitionError(
                code="QUEST_NOT_FOUND",
                detail=f"Chain-unlock target not found: quest_id={next_quest_id}",
            )
        title: str = quest_node.get("description") or next_quest_id
        meta = _make_chain_meta(quest_id=next_quest_id, player_id=player_id)
        return await self._offer_service.offer_quest(
            quest_id=next_quest_id,
            player_id=player_id,
            title=title,
            objectives=[],
            item_rewards=[],
            currency_reward=None,
            meta=meta,
        )
