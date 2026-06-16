"""
Module: quest_handler
Layer: engines
Purpose: Handles quest interaction proposals — propose_quest opens a session snapshot,
         claim_completion verifies objectives and triggers lifecycle transitions,
         give_item with a matching deliver target is intercepted as an implicit claim.
Does NOT: read graph state directly (goes through InteractionGraphPort); all lifecycle
          writes go through QuestLifecycleEngine. Does not call LLM or issue HTTP requests.
Dependencies injected: InteractionGraphPort (reads) + AsyncSession + QuestLifecycleEngine
          (the session is forwarded only to the still-session-based lifecycle engine).
Used by: api.routes.interaction
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import TYPE_CHECKING

from neo4j import AsyncSession

from npc_engine.engines.interaction.models import (
    STATUS_OPEN,
    STATUS_PENDING_CONFIRM,
    UI_DIRECTIVE_NONE,
    UI_DIRECTIVE_QUEST,
    UI_DIRECTIVE_REWARD,
    InteractionProposal,
    InteractionState,
)
from npc_engine.engines.interaction.quest_verifier import verify_objectives
from npc_engine.engines.quest.models import QuestObjectiveInput, QuestTransitionMeta
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine

if TYPE_CHECKING:
    from npc_engine.engines.ports.interaction_port import InteractionGraphPort

_logger = logging.getLogger(__name__)

_HINT_NOT_MET = "npc_refuses_objective_not_met"
_HINT_NO_QUEST = "npc_no_active_quest"


def _build_meta(*, player_id: str, quest_id: str, reason: str) -> QuestTransitionMeta:
    """Construct server-generated transition metadata for quest lifecycle events."""
    request_id = str(uuid.uuid4())
    idempotency_key = str(uuid.uuid4())
    raw = f"{quest_id}:{player_id}:{reason}"
    idempotency_request_hash = hashlib.sha256(raw.encode()).hexdigest()
    return QuestTransitionMeta(
        request_id=request_id,
        actor_id=player_id,
        reason=reason,
        idempotency_key=idempotency_key,
        idempotency_request_hash=idempotency_request_hash,
    )


async def handle_propose_quest(
    *,
    repo: InteractionGraphPort,
    proposal: InteractionProposal,
    player_id: str,
    npc_id: str,
    engine: QuestLifecycleEngine,
) -> InteractionState:
    """Open a quest proposal session snapshot for (player, quest).

    Loads the current QuestState for the quest identified by target_id and
    returns a show_quest_panel directive with the state snapshot. If no quest
    state exists, returns a no-op open state.

    Args:
        repo: Interaction graph read port.
        proposal: InteractionProposal with kind="propose_quest".
        player_id: Player character ID.
        npc_id: NPC character ID (quest giver).
        engine: QuestLifecycleEngine (unused here; kept for dispatch symmetry).

    Returns:
        InteractionState with ui_directive=show_quest_panel and quest snapshot in data.
    """
    quest_id = proposal.target_id or proposal.payload.get("quest_id")
    if not quest_id:
        _logger.warning("propose_quest has no target_id or quest_id in payload — npc_id=%s player=%s", npc_id, player_id)
        return InteractionState(status=STATUS_OPEN, ui_directive=UI_DIRECTIVE_NONE, narration_hint=_HINT_NO_QUEST)

    state_payload = await repo.get_quest_state(quest_id=quest_id, player_id=player_id)
    if state_payload is None:
        _logger.info("propose_quest: no QuestState for quest_id=%s player=%s", quest_id, player_id)
        return InteractionState(status=STATUS_OPEN, ui_directive=UI_DIRECTIVE_NONE, narration_hint=_HINT_NO_QUEST)

    return InteractionState(
        status=STATUS_OPEN,
        ui_directive=UI_DIRECTIVE_QUEST,
        data=state_payload,
    )


async def handle_claim_completion(
    *,
    repo: InteractionGraphPort,
    session: AsyncSession,
    proposal: InteractionProposal,
    player_id: str,
    npc_id: str,
    engine: QuestLifecycleEngine,
) -> InteractionState:
    """Verify quest objectives and progress the lifecycle when all are satisfied.

    Loads the active QuestState, runs the graph-based verifier against all
    objectives. If all pass: calls update_objective and evaluate_completion via
    the engine; returns pending_confirm with reward overlay directive. If any
    fail: returns open with a narration hint for the NPC to refuse.

    Args:
        repo: Interaction graph read port (quest-state read + objective verification).
        session: Active Neo4j async session, forwarded to the lifecycle engine only.
        proposal: InteractionProposal with kind="claim_completion".
        player_id: Player character ID.
        npc_id: NPC character ID (quest giver).
        engine: QuestLifecycleEngine for lifecycle transitions.

    Returns:
        InteractionState with status=pending_confirm if verified,
        status=open with npc_refuses_objective_not_met hint if not.
    """
    quest_id = proposal.target_id or proposal.payload.get("quest_id")
    if not quest_id:
        _logger.warning("claim_completion has no quest_id — player=%s npc=%s", player_id, npc_id)
        return InteractionState(status=STATUS_OPEN, ui_directive=UI_DIRECTIVE_NONE, narration_hint=_HINT_NO_QUEST)

    state_payload = await repo.get_quest_state(quest_id=quest_id, player_id=player_id)
    if state_payload is None:
        return InteractionState(status=STATUS_OPEN, ui_directive=UI_DIRECTIVE_NONE, narration_hint=_HINT_NO_QUEST)

    if state_payload.get("status") not in {"accepted", "in_progress"}:
        _logger.info("claim_completion: quest not active status=%s", state_payload.get("status"))
        return InteractionState(status=STATUS_OPEN, ui_directive=UI_DIRECTIVE_NONE, narration_hint=_HINT_NO_QUEST)

    raw_objectives = state_payload.get("objectives", [])
    objectives: list[QuestObjectiveInput] = [QuestObjectiveInput.model_validate(o) for o in raw_objectives]

    satisfied = await verify_objectives(repo, player_id, objectives)
    if not satisfied:
        return InteractionState(status=STATUS_OPEN, ui_directive=UI_DIRECTIVE_QUEST, narration_hint=_HINT_NOT_MET)

    meta = _build_meta(player_id=player_id, quest_id=quest_id, reason="claim_completion")
    for obj in objectives:
        current_progress = state_payload.get("objective_progress", {}).get(obj.objective_id, 0)
        delta = max(0, obj.target_count - current_progress)
        if delta > 0:
            try:
                await engine.update_objective(
                    session=session,
                    quest_id=quest_id,
                    player_id=player_id,
                    objective_id=obj.objective_id,
                    progress_delta=delta,
                    meta=meta,
                )
            except Exception as exc:
                _logger.warning("update_objective failed for %s: %s", obj.objective_id, exc)

    eval_meta = _build_meta(player_id=player_id, quest_id=quest_id, reason="evaluate_completion")
    stored = await engine.evaluate_completion(
        session=session,
        quest_id=quest_id,
        player_id=player_id,
        meta=eval_meta,
    )

    if stored.get("status") == "completed":
        return InteractionState(
            status=STATUS_PENDING_CONFIRM,
            ui_directive=UI_DIRECTIVE_REWARD,
            data=stored,
        )

    return InteractionState(status=STATUS_OPEN, ui_directive=UI_DIRECTIVE_QUEST, narration_hint=_HINT_NOT_MET)


async def handle_give_item_as_quest_claim(
    *,
    repo: InteractionGraphPort,
    session: AsyncSession,
    proposal: InteractionProposal,
    player_id: str,
    npc_id: str,
    engine: QuestLifecycleEngine,
) -> InteractionState | None:
    """Intercept give_item when the target_id matches an active quest deliver objective.

    Checks whether any active quest for (player, npc) has a deliver objective
    whose target_id matches the item being given. If so, routes through
    claim_completion logic. Returns None when no quest intercept applies
    (caller should fall through to normal give_item processing).

    Args:
        repo: Interaction graph read port (active-quest lookup).
        session: Active Neo4j async session, forwarded to the lifecycle engine only.
        proposal: InteractionProposal with kind="give_item".
        player_id: Player character ID.
        npc_id: NPC character ID.
        engine: QuestLifecycleEngine for lifecycle transitions.

    Returns:
        InteractionState if the give_item was intercepted as a quest claim,
        or None if no quest deliver match was found.
    """
    item_id = proposal.target_id or proposal.payload.get("item_id")
    if not item_id:
        return None

    active_quest = await repo.get_active_quest_for_player(player_id=player_id)
    if active_quest is None:
        return None

    objectives = active_quest.get("objectives_json") or active_quest.get("objectives") or []
    if isinstance(objectives, str):
        import json
        objectives = json.loads(objectives)

    for raw_obj in objectives:
        obj_type = raw_obj.get("objective_type", "deliver")
        obj_target = raw_obj.get("target_id")
        if obj_type == "deliver" and obj_target == item_id:
            quest_id = active_quest.get("quest_id")
            if not quest_id:
                return None
            quest_giver_id = active_quest.get("quest_giver_id") or npc_id
            if quest_giver_id != npc_id:
                _logger.info("give_item intercept: quest giver=%s != current npc=%s, skip", quest_giver_id, npc_id)
                return None
            claim_proposal = InteractionProposal(kind="claim_completion", target_id=quest_id, payload={})
            return await handle_claim_completion(
                repo=repo,
                session=session,
                proposal=claim_proposal,
                player_id=player_id,
                npc_id=npc_id,
                engine=engine,
            )

    return None
