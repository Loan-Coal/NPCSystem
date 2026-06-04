"""
quest_lifecycle_engine.py - P3 quest lifecycle orchestration service.

Does NOT: expose HTTP routing concerns.

Dependencies injected: Settings and graph/session collaborators.
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.engines.quest.models import (
    QuestObjectiveInput,
    QuestRewardCurrency,
    QuestRewardItem,
    QuestStateRecord,
    QuestTransitionMeta,
)
from npc_engine.engines.quest.quest_engine_helpers import (
    build_lifecycle_event,
    ensure_transaction_session,
    is_trusted_reward_source,
    normalize_item_rewards,
)
from npc_engine.graph.currency_writer import get_character_balance
from npc_engine.graph.event_writer import upsert_quest_lifecycle_event
from npc_engine.graph.graph_writer import apply_currency_transfer, apply_item_transfer
from npc_engine.graph.quest_node_service import get_quest
from npc_engine.graph.quest_writer import create_quest_state_if_absent, get_quest_state, update_quest_node_status, upsert_quest_state
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.utils.errors import QuestTransitionError


_logger = logging.getLogger(__name__)

STATUS_DRAFT = "draft"
STATUS_OFFERED = "offered"
STATUS_ACCEPTED = "accepted"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"


class QuestLifecycleEngine:
    """Quest lifecycle state machine with reward routing and provenance-backed events."""

    def __init__(self, settings: Settings, registry: TypeRegistry | None = None) -> None:
        """Initialise the quest lifecycle engine.

        Args:
            settings: Application settings (used for currency transfer configuration).
            registry: Type registry providing event node model; must be injected
                by the composition root (``api/dependency_singletons.py``).
        Raises:
            ValueError: If registry is None (must be injected via __init__).
        """

        self._settings = settings
        if registry is None:
            raise ValueError("QuestLifecycleEngine requires a TypeRegistry injected via __init__")
        self._registry = registry

    async def _require_state(self, *, session: AsyncSession, quest_id: str, player_id: str) -> QuestStateRecord:
        payload = await get_quest_state(session=session, quest_id=quest_id, player_id=player_id)
        if payload is None:
            raise QuestTransitionError(
                code="QUEST_NOT_FOUND",
                detail=f"Quest state not found for quest_id={quest_id}, player_id={player_id}",
            )
        return QuestStateRecord.model_validate(payload)

    async def _emit_lifecycle_event(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        event_type: str,
        summary: str,
        meta: QuestTransitionMeta,
    ) -> None:
        ensure_transaction_session(session=session)
        event = build_lifecycle_event(
            registry=self._registry,
            quest_id=quest_id,
            player_id=player_id,
            event_type=event_type,
            summary=summary,
            meta=meta,
        )
        tx = await session.begin_transaction()
        async with tx:
            await upsert_quest_lifecycle_event(tx=tx, event=event)
            await tx.commit()

    async def _persist_state_and_event(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        state_payload: dict,
        event_type: str,
        summary: str,
        meta: QuestTransitionMeta,
    ) -> dict:
        ensure_transaction_session(session=session)
        event = build_lifecycle_event(
            registry=self._registry,
            quest_id=quest_id,
            player_id=player_id,
            event_type=event_type,
            summary=summary,
            meta=meta,
        )
        tx = await session.begin_transaction()
        async with tx:
            stored = await upsert_quest_state(
                session=tx,
                quest_id=quest_id,
                player_id=player_id,
                state_payload=state_payload,
            )
            await upsert_quest_lifecycle_event(tx=tx, event=event)
            await tx.commit()
            return stored

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
        if quest_node.get("status") != STATUS_DRAFT:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest must be in draft status to be offered; current status={quest_node.get('status')}",
            )
        await update_quest_node_status(session=session, quest_id=quest_id, status=STATUS_OFFERED)
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
            status=STATUS_OFFERED,
            objectives=objectives,
            objective_progress=progress,
            item_rewards=item_rewards,
            currency_reward=currency_reward,
            rewards_applied=False,
        )
        ensure_transaction_session(session=session)

        tx = await session.begin_transaction()
        async with tx:
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
            if offered_state.status != STATUS_OFFERED:
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
            await tx.commit()
            return offered_state.model_dump(mode="python")

    async def accept_quest(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict:
        """Accept a quest currently in offered state.

        Args:
            session: Active Neo4j async session capable of starting transactions.
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict with status ``"accepted"``.

        Raises:
            QuestTransitionError: If quest is not in offered or accepted state.
        """

        state = await self._require_state(session=session, quest_id=quest_id, player_id=player_id)
        if state.status == STATUS_ACCEPTED:
            await self._emit_lifecycle_event(
                session=session,
                quest_id=quest_id,
                player_id=player_id,
                event_type="quest_accepted",
                summary=f"Quest accepted: {state.title}",
                meta=meta,
            )
            return state.model_dump(mode="python")
        if state.status != STATUS_OFFERED:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest cannot be accepted from status={state.status}",
            )

        next_state = state.model_copy(update={"status": STATUS_ACCEPTED})
        stored = await self._persist_state_and_event(
            session=session,
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state.model_dump(mode="python"),
            event_type="quest_accepted",
            summary=f"Quest accepted: {state.title}",
            meta=meta,
        )
        await update_quest_node_status(session=session, quest_id=quest_id, status=STATUS_ACCEPTED)
        return stored

    async def update_objective(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        objective_id: str,
        progress_delta: int,
        meta: QuestTransitionMeta,
    ) -> dict:
        """Apply objective progress delta and transition into in_progress when applicable.

        Args:
            session: Active Neo4j async session capable of starting transactions.
            quest_id: Quest identifier.
            player_id: Player identifier.
            objective_id: Objective to update.
            progress_delta: Signed integer added to current objective progress.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict with updated objective progress.

        Raises:
            QuestTransitionError: If quest is not in accepted or in_progress state,
                or if objective_id is not found.
        """

        state = await self._require_state(session=session, quest_id=quest_id, player_id=player_id)
        if state.status not in {STATUS_ACCEPTED, STATUS_IN_PROGRESS}:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest objective cannot be updated from status={state.status}",
            )
        if objective_id not in state.objective_progress:
            raise QuestTransitionError(
                code="QUEST_OBJECTIVE_UNKNOWN",
                detail=f"Objective not found: {objective_id}",
            )

        existing_progress = state.objective_progress[objective_id]
        updated_progress = max(0, existing_progress + progress_delta)
        next_progress = {**state.objective_progress, objective_id: updated_progress}

        next_state = state.model_copy(
            update={
                "status": STATUS_IN_PROGRESS,
                "objective_progress": next_progress,
            }
        )
        return await self._persist_state_and_event(
            session=session,
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state.model_dump(mode="python"),
            event_type="quest_objective_updated",
            summary=f"Quest objective updated: {objective_id}",
            meta=meta,
        )

    async def evaluate_completion(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict:
        """Evaluate objective completion and set completed status when all targets are met.

        Args:
            session: Active Neo4j async session capable of starting transactions.
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict with status ``"completed"`` or ``"in_progress"``.

        Raises:
            QuestTransitionError: If quest is not in accepted, in_progress, or completed state.
        """

        state = await self._require_state(session=session, quest_id=quest_id, player_id=player_id)
        if state.status not in {STATUS_ACCEPTED, STATUS_IN_PROGRESS, STATUS_COMPLETED}:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest completion cannot be evaluated from status={state.status}",
            )

        is_completed = all(
            state.objective_progress.get(objective.objective_id, 0) >= objective.target_count
            for objective in state.objectives
        )
        next_status = STATUS_COMPLETED if is_completed else STATUS_IN_PROGRESS
        next_state = state.model_copy(update={"status": next_status})

        stored = await self._persist_state_and_event(
            session=session,
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state.model_dump(mode="python"),
            event_type="quest_completed" if is_completed else "quest_incomplete",
            summary=(
                f"Quest completed: {state.title}" if is_completed else f"Quest incomplete: {state.title}"
            ),
            meta=meta,
        )
        if is_completed:
            await update_quest_node_status(session=session, quest_id=quest_id, status=STATUS_COMPLETED)
        return stored

    async def apply_rewards(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict:
        """Apply quest rewards by routing item and currency writes through graph coordinators.

        Args:
            session: Active Neo4j async session capable of starting transactions.
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict with ``rewards_applied=True``.

        Raises:
            QuestTransitionError: If quest is not completed, or if reward source is not trusted.
        """

        state = await self._require_state(session=session, quest_id=quest_id, player_id=player_id)
        if state.status != STATUS_COMPLETED:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest rewards can only be applied from status={STATUS_COMPLETED}",
            )
        if state.rewards_applied:
            await self._emit_lifecycle_event(
                session=session,
                quest_id=quest_id,
                player_id=player_id,
                event_type="quest_rewards_applied",
                summary=f"Quest rewards applied: {state.title}",
                meta=meta,
            )
            return state.model_dump(mode="python")

        if not is_trusted_reward_source(state.reward_source_id):
            raise QuestTransitionError(
                code="QUEST_REWARD_SOURCE_INVALID",
                detail="Quest reward source must be a trusted system source",
            )

        if state.currency_reward is not None and state.reward_source_id != "system":
            balance = await get_character_balance(session=session, character_id=state.reward_source_id)
            if balance is None or balance < state.currency_reward.amount:
                raise QuestTransitionError(
                    code="QUEST_REWARD_SOURCE_INSUFFICIENT",
                    detail=f"NPC {state.reward_source_id} cannot afford {state.currency_reward.amount}",
                )

        normalized_item_rewards = normalize_item_rewards(state.item_rewards)
        for item_reward in normalized_item_rewards:
            reward_item_idempotency_key = f"quest:{quest_id}:{player_id}:item:{item_reward.item_id}"
            await apply_item_transfer(
                session=session,
                source_id=state.reward_source_id,
                destination_id=player_id,
                item_id=item_reward.item_id,
                quantity=item_reward.quantity,
                reason=f"quest_reward:{quest_id}",
                request_id=meta.request_id,
                idempotency_key=reward_item_idempotency_key,
                transfer_kind="quest_reward",
            )

        if state.currency_reward is not None:
            reward_currency_idempotency_key = f"quest:{quest_id}:{player_id}:currency"
            await apply_currency_transfer(
                session=session,
                settings=self._settings,
                source_id=state.reward_source_id,
                destination_id=player_id,
                amount=state.currency_reward.amount,
                reason=f"quest_reward:{quest_id}",
                request_id=meta.request_id,
                idempotency_key=reward_currency_idempotency_key,
                session_scope=f"quest:{quest_id}:{player_id}",
                transfer_kind="quest_reward",
            )

        if state.reward_source_id != "system":
            for obj in state.objectives:
                if obj.objective_type == "deliver" and obj.target_id is not None:
                    deliver_idempotency_key = f"quest:{quest_id}:{player_id}:deliver:{obj.objective_id}"
                    try:
                        await apply_item_transfer(
                            session=session,
                            source_id=player_id,
                            destination_id=state.reward_source_id,
                            item_id=obj.target_id,
                            quantity=obj.target_count,
                            reason=f"quest_deliver:{quest_id}",
                            request_id=meta.request_id,
                            idempotency_key=deliver_idempotency_key,
                            transfer_kind="quest_deliver",
                        )
                    except Exception:
                        _logger.warning("deliver transfer failed for item %s — item may already be gone", obj.target_id)

        next_state = state.model_copy(update={"rewards_applied": True})
        return await self._persist_state_and_event(
            session=session,
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state.model_dump(mode="python"),
            event_type="quest_rewards_applied",
            summary=f"Quest rewards applied: {state.title}",
            meta=meta,
        )
