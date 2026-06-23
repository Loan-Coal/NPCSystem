"""
Module: quest
Layer: api
Purpose: v1 quest lifecycle route handlers, including choice-based branching (EXP-218).
Does NOT: execute direct Cypher writes in route handlers or hold a Neo4j session (DEC-122).
Dependencies: fastapi, npc_engine.api.dependencies_engines, npc_engine.api.quest_helpers,
              npc_engine.api.route_helpers, npc_engine.api.schemas, npc_engine.config,
              npc_engine.engines.quest.models, npc_engine.engines.quest.quest_chain_resolver,
              npc_engine.engines.quest.quest_lifecycle_engine,
              npc_engine.engines.quest.quest_offer_service,
              npc_engine.engines.quest.quest_reward_router, npc_engine.utils.errors
Dependencies injected: QuestChainResolver, QuestLifecycleEngine, QuestOfferService,
    QuestRewardRouter, Settings (via FastAPI Depends).
Used by: api.router
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from npc_engine.api.dependencies import get_quest_lifecycle_engine
from npc_engine.api.dependencies_engines import (
    get_quest_chain_resolver,
    get_quest_offer_service,
    get_quest_reward_router,
)
from npc_engine.api.helpers import (
    build_transition_meta,
    quest_error_to_http,
    to_objective_inputs,
)
from npc_engine.api.helpers import OkEnvelope, ok_response
from npc_engine.api.schemas import (
    QuestAcceptRequest,
    QuestChooseRequest,
    QuestChooseResponse,
    QuestEvaluateRequest,
    QuestObjectiveUpdateRequest,
    QuestOfferRequest,
    QuestRewardApplyRequest,
)
from npc_engine.config import Settings, get_settings
from npc_engine.engines.quest.models import QuestRewardCurrency, QuestRewardItem
from npc_engine.engines.quest.quest_chain_resolver import QuestChainResolver
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.engines.quest.quest_offer_service import QuestOfferService
from npc_engine.engines.quest.quest_reward_router import QuestRewardRouter
from npc_engine.utils.errors import QuestTransitionError


router = APIRouter(prefix="/quest")


@router.post("/offer-draft", response_model=OkEnvelope[dict[str, Any]])
async def offer_draft_quest(
    body: QuestOfferRequest,
    http_request: Request,
    offer_service: QuestOfferService = Depends(get_quest_offer_service),
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
        state = await offer_service.offer_draft_quest(
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


@router.post("/offer", response_model=OkEnvelope[dict[str, Any]])
async def offer_quest(
    body: QuestOfferRequest,
    http_request: Request,
    offer_service: QuestOfferService = Depends(get_quest_offer_service),
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
        state = await offer_service.offer_quest(
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


@router.post("/accept", response_model=OkEnvelope[dict[str, Any]])
async def accept_quest(
    body: QuestAcceptRequest,
    http_request: Request,
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
            quest_id=body.quest_id,
            player_id=body.player_id,
            meta=meta,
        )
    except QuestTransitionError as error:
        raise quest_error_to_http(error) from error
    return ok_response({"quest_state": state})


@router.post("/objective", response_model=OkEnvelope[dict[str, Any]])
async def update_objective(
    body: QuestObjectiveUpdateRequest,
    http_request: Request,
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
            quest_id=body.quest_id,
            player_id=body.player_id,
            objective_id=body.objective_id,
            progress_delta=body.progress_delta,
            meta=meta,
        )
    except QuestTransitionError as error:
        raise quest_error_to_http(error) from error
    return ok_response({"quest_state": state})


@router.post("/evaluate", response_model=OkEnvelope[dict[str, Any]])
async def evaluate_completion(
    body: QuestEvaluateRequest,
    http_request: Request,
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
            quest_id=body.quest_id,
            player_id=body.player_id,
            meta=meta,
        )
    except QuestTransitionError as error:
        raise quest_error_to_http(error) from error
    return ok_response({"quest_state": state})


@router.post("/reward", response_model=OkEnvelope[dict[str, Any]])
async def apply_rewards(
    body: QuestRewardApplyRequest,
    http_request: Request,
    reward_router: QuestRewardRouter = Depends(get_quest_reward_router),
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
        state = await reward_router.apply_rewards(
            quest_id=body.quest_id,
            player_id=body.player_id,
            meta=meta,
        )
    except QuestTransitionError as error:
        raise quest_error_to_http(error) from error
    return ok_response({"quest_state": state})


@router.post("/{quest_id}/choose", response_model=OkEnvelope[QuestChooseResponse])
async def choose_quest_branch(
    quest_id: str,
    body: QuestChooseRequest,
    resolver: QuestChainResolver = Depends(get_quest_chain_resolver),
) -> dict[str, Any]:
    """Select the quest branch that matches the player's choice.

    Finds the UNLOCKS edge whose ``on_choice_id`` equals ``body.choice_id`` and
    offers the successor quest to the player. If no matching edge exists (including
    all-null ``on_choice_id`` edges), ``next_quest_id`` is ``null`` and no quest is
    offered — preserving auto-unlock back-compat.

    Args:
        quest_id: Source quest node ID (from URL path).
        body: Validated request body containing ``player_id`` and ``choice_id``.
        resolver: Injected QuestChainResolver (singleton from composition root).

    Returns:
        OkEnvelope with QuestChooseResponse payload.
    """
    next_quest_id = await resolver.choose(
        quest_id=quest_id,
        player_id=body.player_id,
        choice_id=body.choice_id,
    )
    return ok_response(
        QuestChooseResponse(
            quest_id=quest_id,
            player_id=body.player_id,
            next_quest_id=next_quest_id,
        ).model_dump()
    )
