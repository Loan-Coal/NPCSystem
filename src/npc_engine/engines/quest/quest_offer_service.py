"""
Module: quest_offer_service
Layer: engines
Purpose: Quest offer operations — transitions a draft Quest node to offered status and
    creates per-player QuestState nodes for the offered lifecycle phase.
Dependencies: npc_engine.config, npc_engine.engines.quest.models,
    npc_engine.engines.quest.quest_engine_helpers, npc_engine.engines.ports.quest_port,
    npc_engine.type_registry, npc_engine.utils.errors.
Used by: api.routes.quest (via dependency injection).

Does NOT: perform state machine transitions beyond offered (accept/update/evaluate live in
    quest_lifecycle_engine). Does NOT: apply rewards.
    Does NOT: hold a Neo4j session (DEC-122 / SEV-24).
Dependencies injected: Settings, TypeRegistry, QuestOfferGraphPort (via __init__).
"""

from __future__ import annotations

from typing import Any

import logging

from npc_engine.config import Settings
from npc_engine.engines.ports.quest_port import QuestOfferGraphPort
from npc_engine.engines.quest.models import (
    QuestObjectiveInput,
    QuestRewardCurrency,
    QuestRewardItem,
    QuestStateRecord,
    QuestStatus,
    QuestTransitionMeta,
)
from npc_engine.engines.quest.quest_engine_helpers import (
    build_lifecycle_event,
    is_trusted_reward_source,
)
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.utils.errors import QuestTransitionError


_logger = logging.getLogger(__name__)


class QuestOfferService:
    """Quest offer state machine — creates and validates offered QuestState nodes."""

    def __init__(
        self,
        settings: Settings,
        registry: TypeRegistry | None = None,
        quest_offer_repo: QuestOfferGraphPort | None = None,
    ) -> None:
        """Initialise the quest offer service.

        Args:
            settings: Application settings.
            registry: Type registry providing event node model; required.
            quest_offer_repo: Graph port for quest offer writes (DEC-122 / SEV-24); required.

        Raises:
            ValueError: If registry or quest_offer_repo is None.
        """
        self._settings = settings
        if registry is None:
            raise ValueError("QuestOfferService requires a TypeRegistry injected via __init__")
        if quest_offer_repo is None:
            raise ValueError("QuestOfferService requires a QuestOfferGraphPort injected via __init__")
        self._registry = registry
        self._quest_offer_repo = quest_offer_repo

    async def offer_draft_quest(
        self,
        *,
        quest_id: str,
        player_id: str,
        title: str,
        objectives: list[QuestObjectiveInput],
        item_rewards: list[QuestRewardItem],
        currency_reward: QuestRewardCurrency | None,
        meta: QuestTransitionMeta,
        reward_source_id: str = "system",
    ) -> dict[str, Any]:
        """Transition a generated draft quest to offered status for a specific player.

        Args:
            quest_id: ID of a Quest node in ``draft`` status.
            player_id: Player identifier.
            title: Human-readable quest title.
            objectives: List of quest objective definitions.
            item_rewards: Item rewards to grant on completion.
            currency_reward: Optional currency reward to grant on completion.
            meta: Transition metadata for provenance and idempotency fields.
            reward_source_id: Reward source identifier; must be trusted.

        Returns:
            Persisted quest state payload dict[str, Any] with status ``"offered"``.

        Raises:
            QuestTransitionError: If Quest node not found, not in draft status,
                or reward_source_id is not trusted.
        """
        quest_node = await self._quest_offer_repo.get_quest(quest_id=quest_id)
        if quest_node is None:
            raise QuestTransitionError(
                code="QUEST_NOT_FOUND",
                detail=f"Quest node not found: quest_id={quest_id}",
            )
        if quest_node.get("status") != QuestStatus.DRAFT:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest must be in draft status to be offered; current status={quest_node.get('status')}",
            )
        await self._quest_offer_repo.update_quest_node_status(quest_id=quest_id, status=QuestStatus.OFFERED)
        return await self.offer_quest(
            quest_id=quest_id,
            player_id=player_id,
            title=title,
            objectives=objectives,
            item_rewards=item_rewards,
            currency_reward=currency_reward,
            meta=meta,
            reward_source_id=reward_source_id,
        )

    async def offer_quest(
        self,
        *,
        quest_id: str,
        player_id: str,
        title: str,
        objectives: list[QuestObjectiveInput],
        item_rewards: list[QuestRewardItem],
        currency_reward: QuestRewardCurrency | None,
        meta: QuestTransitionMeta,
        reward_source_id: str = "system",
    ) -> dict[str, Any]:
        """Create or return offered quest state for a player.

        Args:
            quest_id: Quest identifier.
            player_id: Player identifier.
            title: Human-readable quest title.
            objectives: List of quest objective definitions.
            item_rewards: Item rewards to grant on completion.
            currency_reward: Optional currency reward to grant on completion.
            meta: Transition metadata for provenance and idempotency fields.
            reward_source_id: Reward source identifier; must be trusted.

        Returns:
            Persisted quest state payload dict[str, Any] with status ``"offered"``.

        Raises:
            QuestTransitionError: If reward_source_id is not trusted.
        """
        if not is_trusted_reward_source(reward_source_id):
            raise QuestTransitionError(
                code="QUEST_REWARD_SOURCE_INVALID",
                detail="reward_source_id must be a trusted system source",
            )

        progress = {objective.objective_id: 0 for objective in objectives}
        state = QuestStateRecord(
            quest_id=quest_id,
            player_id=player_id,
            reward_source_id=reward_source_id,
            title=title,
            status=QuestStatus.OFFERED,
            objectives=objectives,
            objective_progress=progress,
            item_rewards=item_rewards,
            currency_reward=currency_reward,
            rewards_applied=False,
        )
        event = build_lifecycle_event(
            registry=self._registry,
            quest_id=quest_id,
            player_id=player_id,
            event_type="quest_offered",
            summary=f"Quest offered: {state.title}",
            meta=meta,
        )
        stored = await self._quest_offer_repo.offer_quest_atomic(
            quest_id=quest_id,
            player_id=player_id,
            state_payload=state.model_dump(mode="python"),
            event_node=event,
        )
        offered_state = QuestStateRecord.model_validate(stored)
        if not is_trusted_reward_source(offered_state.reward_source_id):
            raise QuestTransitionError(
                code="QUEST_REWARD_SOURCE_INVALID",
                detail="reward_source_id must be a trusted system source",
            )
        return offered_state.model_dump(mode="python")
