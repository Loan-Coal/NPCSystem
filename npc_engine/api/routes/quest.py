"""
quest.py - v1 quest lifecycle routes.

Does NOT: execute direct Cypher writes in route handlers.

Dependencies injected: AsyncSession, QuestLifecycleEngine, Settings.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from neo4j import AsyncSession

from api.dependencies import get_db_session, get_quest_lifecycle_engine
from api.route_helpers import error_response, ok_response
from api.schemas import (
    QuestAcceptRequest,
    QuestEvaluateRequest,
    QuestObjectiveBody,
    QuestObjectiveUpdateRequest,
    QuestOfferRequest,
    QuestRewardApplyRequest,
)
from config import Settings, get_settings
from engines.quest.models import QuestObjectiveInput, QuestRewardCurrency, QuestRewardItem, QuestTransitionMeta
from engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from utils.errors import QuestTransitionError


IDEMPOTENCY_REQUEST_HASH_HEADER = "X-Idempotency-Request-Hash"


router = APIRouter(prefix="/quest")


def _quest_error_status(error: QuestTransitionError) -> int:
    """Map QuestTransitionError codes to HTTP status codes.

    Args:
        error: QuestTransitionError with a machine-readable code.

    Returns:
        HTTP status code for the error.
    """
    status_code = 500
    if error.code == "QUEST_PROVENANCE_REQUIRED":
        status_code = 400
    if error.code == "QUEST_REWARD_SOURCE_INVALID":
        status_code = 400
    if error.code == "QUEST_NOT_FOUND":
        status_code = 404
    if error.code in {"QUEST_TRANSITION_INVALID", "QUEST_OBJECTIVE_UNKNOWN"}:
        status_code = 409
    if error.code == "QUEST_EVENT_SESSION_INVALID":
        status_code = 500
    return status_code


def _quest_error_to_http(error: QuestTransitionError) -> HTTPException:
    """Convert a QuestTransitionError to a FastAPI HTTPException.

    Args:
        error: QuestTransitionError with code and detail.

    Returns:
        HTTPException with mapped status code and canonical error envelope.
    """
    return HTTPException(
        status_code=_quest_error_status(error),
        detail=error_response(error_code=error.code, message=error.detail),
    )


def _build_transition_meta(*, request: Request, settings: Settings, actor_id: str, reason: str) -> QuestTransitionMeta:
    """Build provenance metadata required for quest lifecycle transitions.

    Args:
        request: Incoming FastAPI request.
        settings: Application settings for header name resolution.
        actor_id: Id of the player initiating the transition.
        reason: Semantic reason label for the transition.

    Returns:
        QuestTransitionMeta with request_id, actor_id, reason, idempotency_key, and request_hash.

    Raises:
        QuestTransitionError: When any required provenance field is missing.
    """
    request_id = request.headers.get("X-Request-ID", "").strip()
    idempotency_key = getattr(request.state, "idempotency_key", "") or request.headers.get(
        settings.IDEMPOTENCY_HEADER_NAME,
        "",
    ).strip()
    idempotency_request_hash = (
        getattr(request.state, "idempotency_request_hash", "")
        or request.headers.get(IDEMPOTENCY_REQUEST_HASH_HEADER, "").strip()
    )

    if request_id == "" or idempotency_key == "" or idempotency_request_hash == "":
        raise QuestTransitionError(
            code="QUEST_PROVENANCE_REQUIRED",
            detail="request_id, idempotency_key, and idempotency_request_hash are required",
        )

    return QuestTransitionMeta(
        request_id=request_id,
        actor_id=actor_id,
        reason=reason,
        idempotency_key=idempotency_key,
        idempotency_request_hash=idempotency_request_hash,
    )


def _to_objective_inputs(items: list[QuestObjectiveBody]) -> list[QuestObjectiveInput]:
    """Convert API objective body dtos to engine input models.

    Args:
        items: List of QuestObjectiveBody from the API request.

    Returns:
        List of QuestObjectiveInput for the quest lifecycle engine.
    """
    return [QuestObjectiveInput(objective_id=item.objective_id, target_count=item.target_count) for item in items]


@router.post("/offer")
async def offer_quest(
    body: QuestOfferRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Offer a quest and create the initial offered lifecycle state."""

    try:
        meta = _build_transition_meta(
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
            objectives=_to_objective_inputs(body.objectives),
            item_rewards=[QuestRewardItem(item_id=item.item_id, quantity=item.quantity) for item in body.item_rewards],
            currency_reward=(
                QuestRewardCurrency(amount=body.currency_reward.amount)
                if body.currency_reward is not None
                else None
            ),
            meta=meta,
        )
    except QuestTransitionError as error:
        raise _quest_error_to_http(error) from error

    return ok_response({"quest_state": state})


@router.post("/accept")
async def accept_quest(
    body: QuestAcceptRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Accept one offered quest for a player."""

    try:
        meta = _build_transition_meta(
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
        raise _quest_error_to_http(error) from error

    return ok_response({"quest_state": state})


@router.post("/objective")
async def update_objective(
    body: QuestObjectiveUpdateRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Apply one quest objective progress update."""

    try:
        meta = _build_transition_meta(
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
        raise _quest_error_to_http(error) from error

    return ok_response({"quest_state": state})


@router.post("/evaluate")
async def evaluate_completion(
    body: QuestEvaluateRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Evaluate quest completion based on objective progress."""

    try:
        meta = _build_transition_meta(
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
        raise _quest_error_to_http(error) from error

    return ok_response({"quest_state": state})


@router.post("/reward")
async def apply_rewards(
    body: QuestRewardApplyRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Apply rewards for one completed quest using converged coordinator write paths."""

    try:
        meta = _build_transition_meta(
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
        raise _quest_error_to_http(error) from error

    return ok_response({"quest_state": state})
