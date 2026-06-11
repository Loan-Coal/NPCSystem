"""
Module: quest_lifecycle_engine
Layer: engines
Purpose: Quest lifecycle state machine — orchestrates accept, objective-progress, and
    completion transitions for per-player quest state.
Dependencies: npc_engine.config, npc_engine.engines.quest.models,
    npc_engine.engines.quest.quest_engine_helpers, npc_engine.graph.*,
    npc_engine.type_registry, npc_engine.utils.errors.
Used by: api.routes.quest (accept/update/evaluate routes), api.routes.interaction,
    engines.interaction.quest_handler.

Does NOT: handle quest offer flow (see quest_offer_service.QuestOfferService).
          Does NOT: apply rewards (see quest_reward_router.QuestRewardRouter).
Dependencies injected: Settings, TypeRegistry (via __init__); AsyncSession (per method).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from neo4j import AsyncSession, AsyncTransaction

if TYPE_CHECKING:
    from npc_engine.engines.quest.quest_chain_resolver import QuestChainResolver

from npc_engine.config import Settings
from npc_engine.engines.quest.models import (
    QuestStateRecord,
    QuestStatus,
    QuestTransitionMeta,
)
from npc_engine.engines.quest.quest_engine_helpers import (
    build_lifecycle_event,
    ensure_transaction_session,
)
from npc_engine.graph.event_writer import upsert_quest_lifecycle_event
from npc_engine.graph.quest_writer import get_quest_state, update_quest_node_status, upsert_quest_state
from npc_engine.graph.transaction_coordinator import run_in_tx
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.utils.errors import QuestTransitionError


_logger = logging.getLogger(__name__)


class QuestLifecycleEngine:
    """Quest lifecycle state machine — accept, objective progress, and completion transitions."""

    def __init__(
        self,
        settings: Settings,
        registry: TypeRegistry | None = None,
        chain_resolver: QuestChainResolver | None = None,
    ) -> None:
        """Initialise the quest lifecycle engine.

        Args:
            settings: Application settings (kept for interface symmetry with other engines).
            registry: Type registry providing event node model; must be injected
                by the composition root (``api/dependency_singletons.py``).
            chain_resolver: Optional injected QuestChainResolver. When set, called
                after a COMPLETED transition to offer unlocked successor quests.
                Existing callers that omit this parameter are unaffected.
        Raises:
            ValueError: If registry is None (must be injected via __init__).
        """
        self._settings = settings
        if registry is None:
            raise ValueError("QuestLifecycleEngine requires a TypeRegistry injected via __init__")
        self._registry = registry
        self._chain_resolver = chain_resolver

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
        async def _work(tx: AsyncTransaction) -> None:
            await upsert_quest_lifecycle_event(tx=tx, event=event)

        await run_in_tx(session, _work)

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
        async def _work(tx: AsyncTransaction) -> dict:
            stored = await upsert_quest_state(
                session=tx,
                quest_id=quest_id,
                player_id=player_id,
                state_payload=state_payload,
            )
            await upsert_quest_lifecycle_event(tx=tx, event=event)
            return stored

        return await run_in_tx(session, _work)

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
        if state.status == QuestStatus.ACCEPTED:
            await self._emit_lifecycle_event(
                session=session,
                quest_id=quest_id,
                player_id=player_id,
                event_type="quest_accepted",
                summary=f"Quest accepted: {state.title}",
                meta=meta,
            )
            return state.model_dump(mode="python")
        if state.status != QuestStatus.OFFERED:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest cannot be accepted from status={state.status}",
            )

        next_state = state.model_copy(update={"status": QuestStatus.ACCEPTED})
        stored = await self._persist_state_and_event(
            session=session,
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state.model_dump(mode="python"),
            event_type="quest_accepted",
            summary=f"Quest accepted: {state.title}",
            meta=meta,
        )
        await update_quest_node_status(session=session, quest_id=quest_id, status=QuestStatus.ACCEPTED)
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
        if state.status not in {QuestStatus.ACCEPTED, QuestStatus.IN_PROGRESS}:
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
                "status": QuestStatus.IN_PROGRESS,
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
        if state.status not in {QuestStatus.ACCEPTED, QuestStatus.IN_PROGRESS, QuestStatus.COMPLETED}:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest completion cannot be evaluated from status={state.status}",
            )

        is_completed = all(
            state.objective_progress.get(objective.objective_id, 0) >= objective.target_count
            for objective in state.objectives
        )
        next_status = QuestStatus.COMPLETED if is_completed else QuestStatus.IN_PROGRESS
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
            await update_quest_node_status(session=session, quest_id=quest_id, status=QuestStatus.COMPLETED)
            if self._chain_resolver is not None:
                await self._chain_resolver.resolve(
                    session=session,
                    quest_id=quest_id,
                    player_id=player_id,
                    outcome="complete",
                )
        return stored

    _TERMINAL_STATUSES = frozenset({QuestStatus.COMPLETED, QuestStatus.FAILED, QuestStatus.EXPIRED})

    async def fail_quest(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict:
        """Transition a quest to failed status and resolve any UNLOCKS(on_outcome:fail) chains.

        Args:
            session: Active Neo4j async session capable of starting transactions.
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict with status ``"failed"``.

        Raises:
            QuestTransitionError: If quest is already in a terminal state.
        """
        state = await self._require_state(session=session, quest_id=quest_id, player_id=player_id)
        if state.status in self._TERMINAL_STATUSES:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest cannot be failed from terminal status={state.status}",
            )
        next_state = state.model_copy(update={"status": QuestStatus.FAILED})
        stored = await self._persist_state_and_event(
            session=session,
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state.model_dump(mode="python"),
            event_type="quest_failed",
            summary=f"Quest failed: {state.title}",
            meta=meta,
        )
        await self._apply_fail_side_effects(session=session, quest_id=quest_id, player_id=player_id)
        return stored

    async def _apply_fail_side_effects(
        self, *, session: AsyncSession, quest_id: str, player_id: str
    ) -> None:
        await update_quest_node_status(session=session, quest_id=quest_id, status=QuestStatus.FAILED)
        if self._chain_resolver is not None:
            await self._chain_resolver.resolve(
                session=session, quest_id=quest_id, player_id=player_id, outcome="fail"
            )
