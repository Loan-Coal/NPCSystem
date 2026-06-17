"""
Module: quest_reward_router
Layer: engines
Purpose: Quest reward routing — atomic delivery collection, item grant, and currency transfer
    within a single Neo4j transaction once a quest reaches completed status.
Dependencies: npc_engine.config, npc_engine.engines.quest.models,
    npc_engine.engines.quest.quest_engine_helpers, npc_engine.engines.ports.quest_port,
    npc_engine.type_registry, npc_engine.utils.errors.
Used by: api.routes.quest (via dependency injection).

Does NOT: perform state machine transitions (accept/update/evaluate live in
    quest_lifecycle_engine). Does NOT: handle offer flow.
    Does NOT: hold a Neo4j session (DEC-122 / SEV-24).
Dependencies injected: Settings, TypeRegistry, QuestRewardGraphPort (via __init__).
"""

from __future__ import annotations

from typing import Any

import logging

from npc_engine.config import Settings
from npc_engine.engines.ports.quest_port import QuestRewardGraphPort
from npc_engine.engines.quest.models import (
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


class QuestRewardRouter:
    """Quest reward coordinator — possession check → delivery → item/currency grants."""

    def __init__(
        self,
        settings: Settings,
        registry: TypeRegistry | None = None,
        quest_reward_repo: QuestRewardGraphPort | None = None,
    ) -> None:
        """Initialise the quest reward router.

        Args:
            settings: Application settings (used for currency transfer configuration).
            registry: Type registry providing event node model; required.
            quest_reward_repo: Graph port for reward delivery (DEC-122 / SEV-24); required.

        Raises:
            ValueError: If registry or quest_reward_repo is None.
        """
        self._settings = settings
        if registry is None:
            raise ValueError("QuestRewardRouter requires a TypeRegistry injected via __init__")
        if quest_reward_repo is None:
            raise ValueError("QuestRewardRouter requires a QuestRewardGraphPort injected via __init__")
        self._registry = registry
        self._quest_reward_repo = quest_reward_repo

    async def _require_state(self, *, quest_id: str, player_id: str) -> QuestStateRecord:
        payload = await self._quest_reward_repo.get_quest_state(quest_id=quest_id, player_id=player_id)
        if payload is None:
            raise QuestTransitionError(
                code="QUEST_NOT_FOUND",
                detail=f"Quest state not found for quest_id={quest_id}, player_id={player_id}",
            )
        return QuestStateRecord.model_validate(payload)

    async def apply_rewards(
        self,
        *,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict[str, Any]:
        """Apply quest rewards atomically: possession check → delivery → grants → state persist.

        Args:
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict[str, Any] with ``rewards_applied=True``.

        Raises:
            QuestTransitionError: If quest not completed, reward source invalid,
                player lacks a delivery item, or delivery transfer fails.
        """
        state = await self._require_state(quest_id=quest_id, player_id=player_id)
        if state.status != QuestStatus.COMPLETED:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest rewards can only be applied from status={QuestStatus.COMPLETED}",
            )
        if state.rewards_applied:
            await self._emit_idempotent_event(
                quest_id=quest_id, player_id=player_id, state=state, meta=meta
            )
            return state.model_dump(mode="python")

        if not is_trusted_reward_source(state.reward_source_id):
            raise QuestTransitionError(
                code="QUEST_REWARD_SOURCE_INVALID",
                detail="Quest reward source must be a trusted system source",
            )
        if state.currency_reward is not None and state.reward_source_id != "system":
            balance = await self._quest_reward_repo.get_character_balance(
                character_id=state.reward_source_id
            )
            if balance is None or balance < state.currency_reward.amount:
                raise QuestTransitionError(
                    code="QUEST_REWARD_SOURCE_INSUFFICIENT",
                    detail=f"NPC {state.reward_source_id} cannot afford {state.currency_reward.amount}",
                )

        next_state = state.model_copy(update={"rewards_applied": True})
        event = build_lifecycle_event(
            registry=self._registry,
            quest_id=quest_id,
            player_id=player_id,
            event_type="quest_rewards_applied",
            summary=f"Quest rewards applied: {state.title}",
            meta=meta,
        )
        return await self._quest_reward_repo.apply_rewards_atomic(
            quest_id=quest_id,
            player_id=player_id,
            request_id=meta.request_id,
            state_dict=state.model_dump(mode="python"),
            next_state_payload=next_state.model_dump(mode="python"),
            event_node=event,
            settings=self._settings,
        )

    async def _emit_idempotent_event(
        self,
        *,
        quest_id: str,
        player_id: str,
        state: QuestStateRecord,
        meta: QuestTransitionMeta,
    ) -> None:
        event = build_lifecycle_event(
            registry=self._registry,
            quest_id=quest_id,
            player_id=player_id,
            event_type="quest_rewards_applied",
            summary=f"Quest rewards applied: {state.title}",
            meta=meta,
        )
        await self._quest_reward_repo.emit_lifecycle_event(event_node=event)
