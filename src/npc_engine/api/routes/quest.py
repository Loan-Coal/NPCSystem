"""
Module: quest
Layer: api
Purpose: v1 quest lifecycle route handlers.
Does NOT: execute direct Cypher writes in route handlers.
Dependencies: fastapi, neo4j, npc_engine.api.dependencies, npc_engine.api.quest_helpers,
              npc_engine.api.route_helpers, npc_engine.api.schemas, npc_engine.config,
              npc_engine.engines.quest.models, npc_engine.engines.quest.quest_lifecycle_engine,
              npc_engine.utils.errors
Dependencies injected: AsyncSession, QuestLifecycleEngine, Settings.
Used by: api.router
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from neo4j import AsyncSession

from npc_engine.api.dependencies import get_db_session, get_quest_lifecycle_engine
from npc_engine.api.quest_helpers import (
    build_transition_meta,
    quest_error_to_http,
    to_objective_inputs,
)
from npc_engine.api.route_helpers import ok_response
from npc_engine.api.schemas import (
    QuestAcceptRequest,
    QuestEvaluateRequest,
    QuestObjectiveUpdateRequest,
    QuestOfferRequest,
    QuestRewardApplyRequest,
)
from npc_engine.config import Settings, get_settings
from npc_engine.engines.quest.models import QuestRewardCurrency, QuestRewardItem
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.utils.errors import QuestTransitionError


router = APIRouter(prefix="/quest")


@router.post("/offer-draft")
async def offer_draft_quest(
    body: QuestOfferRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Transition a generated draft quest to offered status for a player.

    The quest_id must reference a Quest node written by the generator
    (``POST /v1/admin/quests/generate``) with ``status="draft"``.
    """
    try:
        meta = build_transition_meta(
            request=http_request,
            settings=settings,
            actor_id=body.player_id,
            reason="quest_offer_draft",
        )
        state = await engine.offer_draft_quest(
            session=session,
            quest_id=body.quest_id,
            player_id=body.player_id,
            title=body.title,
            objectives=to_objective_inputs(body.objectives),
            item_rewards=[QuestRewardItem(item_id=item.item_id, quantity=item.quantity) for item in body.item_rewards],
            currency_reward=(
                QuestRewardCurrency(amount=body.currency_reward.amount)
                if body.currency_reward is not None
                else None
            ),
            meta=meta,
            reward_source_id=body.reward_source_id,
        )
    except QuestTransitionError as error:
        raise quest_error_to_http(error) from error
    return ok_response({"quest_state": state})


@router.post("/offer")
async def offer_quest(
    body: QuestOfferRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Offer a quest and create the initial offered lifecycle state."""

    try:
        meta = build_transition_meta(
            request=http_request,
            settings=settings,
            actor_id=body.player_id,
            reason="quest_offer",
        )
        state = await engine.offer_quest(
            session=session,
            quest_id=body.quest_id,
            player_id=body.player_id,
            title=body.title,
            objectives=to_objective_inputs(body.objectives),
            item_rewards=[QuestRewardItem(item_id=item.item_id, quantity=item.quantity) for item in body.item_rewards],
            currency_reward=(
                QuestRewardCurrency(amount=body.currency_reward.amount)
                if body.currency_reward is not None
                else None
            ),
            meta=meta,
            reward_source_id=body.reward_source_id,
        )
    except QuestTransitionError as error:
        raise quest_error_to_http(error) from error

    return ok_response({"quest_state": state})


@router.post("/accept")
async def accept_quest(
    body: QuestAcceptRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Accept one offered quest for a player."""

    try:
        meta = build_transition_meta(
            request=http_request,
            settings=settings,
            actor_id=body.player_id,
            reason="quest_accept",
        )
        state = await engine.accept_quest(
            session=session,
            quest_id=body.quest_id,
            player_id=body.player_id,
            meta=meta,
        )
    except QuestTransitionError as error:
        raise quest_error_to_http(error) from error

    return ok_response({"quest_state": state})


@router.post("/objective")
async def update_objective(
    body: QuestObjectiveUpdateRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Apply one quest objective progress update."""

    try:
        meta = build_transition_meta(
            request=http_request,
            settings=settings,
            actor_id=body.player_id,
            reason="quest_objective_update",
        )
        state = await engine.update_objective(
            session=session,
            quest_id=body.quest_id,
            player_id=body.player_id,
            objective_id=body.objective_id,
            progress_delta=body.progress_delta,
            meta=meta,
        )
    except QuestTransitionError as error:
        raise quest_error_to_http(error) from error

    return ok_response({"quest_state": state})


@router.post("/evaluate")
async def evaluate_completion(
    body: QuestEvaluateRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Evaluate quest completion based on objective progress."""

    try:
        meta = build_transition_meta(
            request=http_request,
            settings=settings,
            actor_id=body.player_id,
            reason="quest_evaluate",
        )
        state = await engine.evaluate_completion(
            session=session,
            quest_id=body.quest_id,
            player_id=body.player_id,
            meta=meta,
        )
    except QuestTransitionError as error:
        raise quest_error_to_http(error) from error

    return ok_response({"quest_state": state})


@router.post("/reward")
async def apply_rewards(
    body: QuestRewardApplyRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Apply rewards for one completed quest using converged coordinator write paths."""

    try:
        meta = build_transition_meta(
            request=http_request,
            settings=settings,
            actor_id=body.player_id,
            reason="quest_reward_apply",
        )
        state = await engine.apply_rewards(
            session=session,
            quest_id=body.quest_id,
            player_id=body.player_id,
            meta=meta,
        )
    except QuestTransitionError as error:
        raise quest_error_to_http(error) from error

    return ok_response({"quest_state": state})
