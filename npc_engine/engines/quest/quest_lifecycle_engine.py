"""
quest_lifecycle_engine.py - P3 quest lifecycle orchestration service.

Does NOT: expose HTTP routing concerns.

Dependencies injected: Settings and graph/session collaborators.
"""

from __future__ import annotations

from datetime import datetime, timezone

from neo4j import AsyncSession

from config import Settings
from engines.quest.models import (
    QuestObjectiveInput,
    QuestRewardCurrency,
    QuestRewardItem,
    QuestStateRecord,
    QuestTransitionMeta,
)
from graph.event_writer import upsert_quest_lifecycle_event
from graph.graph_writer import apply_currency_transfer, apply_item_transfer
from graph.node_schemas import EventNode
from graph.quest_writer import create_quest_state_if_absent, get_quest_state, upsert_quest_state
from utils.errors import QuestTransitionError


STATUS_OFFERED = "offered"
STATUS_ACCEPTED = "accepted"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"


class QuestLifecycleEngine:
    """Quest lifecycle state machine with reward routing and provenance-backed events."""

    def __init__(self, settings: Settings):
        self._settings = settings

    @staticmethod
    def _is_trusted_reward_source(reward_source_id: str) -> bool:
        return reward_source_id == "system"

    @staticmethod
    def _normalize_item_rewards(item_rewards: list[QuestRewardItem]) -> list[QuestRewardItem]:
        quantity_by_item_id: dict[str, int] = {}
        for reward in item_rewards:
            quantity_by_item_id[reward.item_id] = quantity_by_item_id.get(reward.item_id, 0) + reward.quantity
        return [
            QuestRewardItem(item_id=item_id, quantity=quantity)
            for item_id, quantity in sorted(quantity_by_item_id.items())
        ]

    @staticmethod
    def _ensure_transaction_session(session: AsyncSession) -> None:
        if not hasattr(session, "begin_transaction"):
            raise QuestTransitionError(
                code="QUEST_EVENT_SESSION_INVALID",
                detail="Quest lifecycle event emission requires a transaction-capable session",
            )

    @staticmethod
    def _build_lifecycle_event(
        *,
        quest_id: str,
        player_id: str,
        event_type: str,
        summary: str,
        meta: QuestTransitionMeta,
    ) -> EventNode:
        now = datetime.now(timezone.utc)
        return EventNode(
            id=f"{quest_id}:{player_id}:{event_type}:{meta.request_id}",
            summary=summary,
            severity=20,
            location_id="quest",
            occurred_at=now,
            tick_id=int(now.timestamp()),
            participants=[player_id],
            event_type=event_type,
            is_public=True,
            producer="quest_lifecycle_engine",
            origin_engine="quest",
            schema_version="v1.4",
            provenance={
                "request_id": meta.request_id,
                "idempotency_key": meta.idempotency_key,
                "idempotency_request_hash": meta.idempotency_request_hash,
                "actor_id": meta.actor_id,
                "reason": meta.reason,
            },
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
        """Create or return offered quest state for a player."""

        if not self._is_trusted_reward_source(reward_source_id):
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
        self._ensure_transaction_session(session=session)

        tx = await session.begin_transaction()
        async with tx:
            stored = await create_quest_state_if_absent(
                session=tx,
                quest_id=quest_id,
                player_id=player_id,
                state_payload=state.model_dump(mode="python"),
            )

            offered_state = QuestStateRecord.model_validate(stored)
            if not self._is_trusted_reward_source(offered_state.reward_source_id):
                raise QuestTransitionError(
                    code="QUEST_REWARD_SOURCE_INVALID",
                    detail="reward_source_id must be a trusted system source",
                )
            if offered_state.status != STATUS_OFFERED:
                raise QuestTransitionError(
                    code="QUEST_TRANSITION_INVALID",
                    detail=f"Quest cannot be re-offered from status={offered_state.status}",
                )

            event = self._build_lifecycle_event(
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
        """Accept a quest currently in offered state."""

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
        """Apply objective progress delta and transition into in_progress when applicable."""

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
        next_progress = dict(state.objective_progress)
        next_progress[objective_id] = updated_progress

        next_state = state.model_copy(
            update={
                "status": STATUS_IN_PROGRESS,
                "objective_progress": next_progress,
            }
        )
        stored = await self._persist_state_and_event(
            session=session,
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state.model_dump(mode="python"),
            event_type="quest_objective_updated",
            summary=f"Quest objective updated: {objective_id}",
            meta=meta,
        )
        return stored

    async def evaluate_completion(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict:
        """Evaluate objective completion and set completed status when all targets are met."""

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
        return stored

    async def apply_rewards(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict:
        """Apply quest rewards by routing item and currency writes through graph coordinators."""

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

        if not self._is_trusted_reward_source(state.reward_source_id):
            raise QuestTransitionError(
                code="QUEST_REWARD_SOURCE_INVALID",
                detail="Quest reward source must be a trusted system source",
            )

        normalized_item_rewards = self._normalize_item_rewards(state.item_rewards)
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

        next_state = state.model_copy(update={"rewards_applied": True})
        stored = await self._persist_state_and_event(
            session=session,
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state.model_dump(mode="python"),
            event_type="quest_rewards_applied",
            summary=f"Quest rewards applied: {state.title}",
            meta=meta,
        )
        return stored

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
        self._ensure_transaction_session(session=session)
        event = self._build_lifecycle_event(
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
        self._ensure_transaction_session(session=session)
        event = self._build_lifecycle_event(
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
