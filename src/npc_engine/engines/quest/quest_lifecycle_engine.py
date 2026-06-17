"""
Module: quest_lifecycle_engine
Layer: engines
Purpose: Quest lifecycle state machine — orchestrates accept, objective-progress, and
    completion transitions for per-player quest state.
Dependencies: npc_engine.config, npc_engine.engines.quest.models,
    npc_engine.engines.quest.quest_engine_helpers, npc_engine.engines.ports.quest_port,
    npc_engine.type_registry, npc_engine.utils.errors.
Used by: api.routes.quest (accept/update/evaluate routes), api.routes.interaction,
    engines.interaction.quest_handler.

Does NOT: handle quest offer flow (see quest_offer_service.QuestOfferService).
          Does NOT: apply rewards (see quest_reward_router.QuestRewardRouter).
          Does NOT: hold a Neo4j session (DEC-122 / SEV-24).
Dependencies injected: Settings, TypeRegistry, QuestLifecycleGraphPort (via __init__).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from npc_engine.config import Settings
from npc_engine.engines.memory.memory_engine import MemoryEngine
from npc_engine.engines.ports.quest_port import QuestLifecycleGraphPort
from npc_engine.engines.quest.models import (
    QuestStateRecord,
    QuestStatus,
    QuestTransitionMeta,
)
from npc_engine.engines.quest.quest_engine_helpers import (
    build_lifecycle_event,
)
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.utils.errors import QuestTransitionError
from npc_engine.world.time_utils import TimePoint

if TYPE_CHECKING:
    from npc_engine.engines.quest.quest_chain_resolver import QuestChainResolver

_logger = logging.getLogger(__name__)


class QuestLifecycleEngine:
    """Quest lifecycle state machine — accept, objective progress, and completion transitions."""

    def __init__(
        self,
        settings: Settings,
        registry: TypeRegistry | None = None,
        chain_resolver: QuestChainResolver | None = None,
        memory_engine: MemoryEngine | None = None,
        quest_repo: QuestLifecycleGraphPort | None = None,
    ) -> None:
        """Initialise the quest lifecycle engine.

        Args:
            settings: Application settings.
            registry: Type registry providing event node model; required.
            chain_resolver: Optional injected QuestChainResolver called after COMPLETED.
            memory_engine: Optional injected MemoryEngine for commitment memory on accept.
            quest_repo: Graph port for quest state reads/writes (DEC-122 / SEV-24); required.

        Raises:
            ValueError: If registry or quest_repo is None.
        """
        self._settings = settings
        if registry is None:
            raise ValueError("QuestLifecycleEngine requires a TypeRegistry injected via __init__")
        if quest_repo is None:
            raise ValueError("QuestLifecycleEngine requires a QuestLifecycleGraphPort injected via __init__")
        self._registry = registry
        self._chain_resolver = chain_resolver
        self._memory_engine = memory_engine
        self._quest_repo = quest_repo

    async def _form_commitment_memory(
        self,
        *,
        quest_id: str,
        player_id: str,
        quest_title: str,
    ) -> None:
        """Form a commitment memory on quest accept (EXP-214). Best-effort — skips on error."""
        if self._memory_engine is None:
            return
        try:
            world_state = await self._quest_repo.get_world_state()
            game_time = TimePoint(
                year=world_state.year,
                season=world_state.season,
                day=world_state.day,
                time_of_day=world_state.time_of_day,
            )
        except Exception:
            _logger.warning(
                "commitment_memory_skipped_no_world_state quest_id=%s player_id=%s",
                quest_id,
                player_id,
            )
            return
        content = f"Player accepted quest '{quest_title}' (id={quest_id})"
        await self._memory_engine.create_from_commitment(
            character_id=player_id,
            content=content,
            game_time=game_time,
            player_id=player_id,
        )

    async def _require_state(self, *, quest_id: str, player_id: str) -> QuestStateRecord:
        payload = await self._quest_repo.get_quest_state(quest_id=quest_id, player_id=player_id)
        if payload is None:
            raise QuestTransitionError(
                code="QUEST_NOT_FOUND",
                detail=f"Quest state not found for quest_id={quest_id}, player_id={player_id}",
            )
        return QuestStateRecord.model_validate(payload)

    async def _emit_lifecycle_event(
        self,
        *,
        quest_id: str,
        player_id: str,
        event_type: str,
        summary: str,
        meta: QuestTransitionMeta,
    ) -> None:
        event = build_lifecycle_event(
            registry=self._registry,
            quest_id=quest_id,
            player_id=player_id,
            event_type=event_type,
            summary=summary,
            meta=meta,
        )
        await self._quest_repo.emit_lifecycle_event(event_node=event)

    async def _persist_state_and_event(
        self,
        *,
        quest_id: str,
        player_id: str,
        state_payload: dict[str, Any],
        event_type: str,
        summary: str,
        meta: QuestTransitionMeta,
    ) -> dict[str, Any]:
        event = build_lifecycle_event(
            registry=self._registry,
            quest_id=quest_id,
            player_id=player_id,
            event_type=event_type,
            summary=summary,
            meta=meta,
        )
        return await self._quest_repo.persist_state_and_event(
            quest_id=quest_id,
            player_id=player_id,
            state_payload=state_payload,
            event_node=event,
        )

    async def accept_quest(
        self,
        *,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict[str, Any]:
        """Accept a quest currently in offered state.

        Args:
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict[str, Any] with status ``"accepted"``.

        Raises:
            QuestTransitionError: If quest is not in offered or accepted state.
        """
        state = await self._require_state(quest_id=quest_id, player_id=player_id)
        if state.status == QuestStatus.ACCEPTED:
            await self._emit_lifecycle_event(
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
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state.model_dump(mode="python"),
            event_type="quest_accepted",
            summary=f"Quest accepted: {state.title}",
            meta=meta,
        )
        await self._quest_repo.update_quest_node_status(quest_id=quest_id, status=QuestStatus.ACCEPTED)
        await self._form_commitment_memory(
            quest_id=quest_id,
            player_id=player_id,
            quest_title=state.title,
        )
        return stored

    async def update_objective(
        self,
        *,
        quest_id: str,
        player_id: str,
        objective_id: str,
        progress_delta: int,
        meta: QuestTransitionMeta,
    ) -> dict[str, Any]:
        """Apply objective progress delta and transition into in_progress when applicable.

        Args:
            quest_id: Quest identifier.
            player_id: Player identifier.
            objective_id: Objective to update.
            progress_delta: Signed integer added to current objective progress.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict[str, Any] with updated objective progress.

        Raises:
            QuestTransitionError: If quest is not in accepted or in_progress state,
                or if objective_id is not found.
        """
        state = await self._require_state(quest_id=quest_id, player_id=player_id)
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
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict[str, Any]:
        """Evaluate objective completion and set completed status when all targets are met.

        Args:
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict[str, Any] with status ``"completed"`` or ``"in_progress"``.

        Raises:
            QuestTransitionError: If quest is not in accepted, in_progress, or completed state.
        """
        state = await self._require_state(quest_id=quest_id, player_id=player_id)
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
            await self._quest_repo.update_quest_node_status(quest_id=quest_id, status=QuestStatus.COMPLETED)
            if self._chain_resolver is not None:
                await self._chain_resolver.resolve(
                    quest_id=quest_id,
                    player_id=player_id,
                    outcome="complete",
                )
        return stored

    _TERMINAL_STATUSES = frozenset({QuestStatus.COMPLETED, QuestStatus.FAILED, QuestStatus.EXPIRED})

    async def fail_quest(
        self,
        *,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict[str, Any]:
        """Transition a quest to failed status and resolve any UNLOCKS(on_outcome:fail) chains.

        Args:
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict[str, Any] with status ``"failed"``.

        Raises:
            QuestTransitionError: If quest is already in a terminal state.
        """
        state = await self._require_state(quest_id=quest_id, player_id=player_id)
        if state.status in self._TERMINAL_STATUSES:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest cannot be failed from terminal status={state.status}",
            )
        next_state = state.model_copy(update={"status": QuestStatus.FAILED})
        stored = await self._persist_state_and_event(
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state.model_dump(mode="python"),
            event_type="quest_failed",
            summary=f"Quest failed: {state.title}",
            meta=meta,
        )
        await self._apply_fail_side_effects(quest_id=quest_id, player_id=player_id)
        return stored

    async def _apply_fail_side_effects(self, *, quest_id: str, player_id: str) -> None:
        await self._quest_repo.update_quest_node_status(quest_id=quest_id, status=QuestStatus.FAILED)
        if self._chain_resolver is not None:
            await self._chain_resolver.resolve(
                quest_id=quest_id, player_id=player_id, outcome="fail"
            )
