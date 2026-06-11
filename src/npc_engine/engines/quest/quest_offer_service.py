"""
Module: quest_offer_service
Layer: engines
Purpose: Quest offer operations — transitions a draft Quest node to offered status and
    creates per-player QuestState nodes for the offered lifecycle phase.
Dependencies: npc_engine.config, npc_engine.engines.quest.models,
    npc_engine.engines.quest.quest_engine_helpers, npc_engine.graph.*,
    npc_engine.type_registry, npc_engine.utils.errors.
Used by: api.routes.quest (via dependency injection).

Does NOT: perform state machine transitions beyond offered (accept/update/evaluate live in
    quest_lifecycle_engine). Does NOT: apply rewards.
Dependencies injected: Settings, TypeRegistry (via __init__); AsyncSession (per method).
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.config import Settings
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
    ensure_transaction_session,
    is_trusted_reward_source,
)
from npc_engine.graph.event_writer import upsert_quest_lifecycle_event
from npc_engine.graph.quest_node_service import get_quest
from npc_engine.graph.quest_writer import (
    create_quest_state_if_absent,
    update_quest_node_status,
)
from npc_engine.graph.transaction_coordinator import run_in_tx
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.utils.errors import QuestTransitionError


_logger = logging.getLogger(__name__)


class QuestOfferService:
    """Quest offer state machine — creates and validates offered QuestState nodes."""

    def __init__(self, settings: Settings, registry: TypeRegistry | None = None) -> None:
        """Initialise the quest offer service.

        Args:
            settings: Application settings (unused currently; kept for symmetry with other engines).
            registry: Type registry providing event node model; must be injected
                by the composition root (``api/dependency_singletons.py``).
        Raises:
            ValueError: If registry is None (must be injected via __init__).
        """
        self._settings = settings
        if registry is None:
            raise ValueError("QuestOfferService requires a TypeRegistry injected via __init__")
        self._registry = registry

    async def offer_draft_quest(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        title: str,
        objectives: list[QuestObjectiveInput],
        item_rewards: list[QuestRewardItem],
        currency_reward: QuestRewardCurrency | None,
        meta: QuestTransitionMeta,
        reward_source_id: str = "system",
    ) -> dict:
        """Transition a generated draft quest to offered status for a specific player.

        Validates that the Quest node exists and is in ``draft`` status (written by
        ``QuestGenerationEngine``), updates it to ``offered``, then creates the initial
        per-player QuestState via ``offer_quest()``.

        Args:
            session: Active Neo4j async session capable of starting transactions.
            quest_id: ID of a Quest node in ``draft`` status (from QuestGenerationEngine).
            player_id: Player identifier.
            title: Human-readable quest title.
            objectives: List of quest objective definitions.
            item_rewards: Item rewards to grant on completion.
            currency_reward: Optional currency reward to grant on completion.
            meta: Transition metadata for provenance and idempotency fields.
            reward_source_id: Reward source identifier; must be a trusted system source.

        Returns:
            Persisted quest state payload dict with status ``"offered"``.

        Raises:
            QuestTransitionError: If Quest node not found, not in draft status,
                or reward_source_id is not trusted.
        """
        quest_node = await get_quest(session=session, quest_id=quest_id)
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
        await update_quest_node_status(session=session, quest_id=quest_id, status=QuestStatus.OFFERED)
        return await self.offer_quest(
            session=session,
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
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        title: str,
        objectives: list[QuestObjectiveInput],
        item_rewards: list[QuestRewardItem],
        currency_reward: QuestRewardCurrency | None,
        meta: QuestTransitionMeta,
        reward_source_id: str = "system",
    ) -> dict:
        """Create or return offered quest state for a player.

        Args:
            session: Active Neo4j async session capable of starting transactions.
            quest_id: Quest identifier.
            player_id: Player identifier.
            title: Human-readable quest title.
            objectives: List of quest objective definitions.
            item_rewards: Item rewards to grant on completion.
            currency_reward: Optional currency reward to grant on completion.
            meta: Transition metadata for provenance and idempotency fields.
            reward_source_id: Reward source identifier; must be a trusted system source.

        Returns:
            Persisted quest state payload dict with status ``"offered"``.

        Raises:
            QuestTransitionError: If reward_source_id is not trusted, or if the quest
                already exists in a non-offered state.
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
        ensure_transaction_session(session=session)

        async def _work(tx: AsyncTransaction) -> dict:
            stored = await create_quest_state_if_absent(
                session=tx,
                quest_id=quest_id,
                player_id=player_id,
                state_payload=state.model_dump(mode="python"),
            )

            offered_state = QuestStateRecord.model_validate(stored)
            if not is_trusted_reward_source(offered_state.reward_source_id):
                raise QuestTransitionError(
                    code="QUEST_REWARD_SOURCE_INVALID",
                    detail="reward_source_id must be a trusted system source",
                )
            if offered_state.status != QuestStatus.OFFERED:
                raise QuestTransitionError(
                    code="QUEST_TRANSITION_INVALID",
                    detail=f"Quest cannot be re-offered from status={offered_state.status}",
                )

            event = build_lifecycle_event(
                registry=self._registry,
                quest_id=quest_id,
                player_id=player_id,
                event_type="quest_offered",
                summary=f"Quest offered: {offered_state.title}",
                meta=meta,
            )
            await upsert_quest_lifecycle_event(tx=tx, event=event)
            return offered_state.model_dump(mode="python")

        return await run_in_tx(session, _work)
