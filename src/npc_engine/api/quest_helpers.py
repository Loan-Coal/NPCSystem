"""
Module: quest_helpers
Layer: api
Purpose: Private helpers for the quest lifecycle route handlers.
Does NOT: define route handlers or access Neo4j directly.
Dependencies: fastapi, npc_engine.api.route_helpers, npc_engine.config,
              npc_engine.engines.quest.models, npc_engine.utils.errors
Dependencies injected: none (pure helpers, all params passed per-call).
Used by: api.routes.quest
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from npc_engine.api.route_helpers import error_response
from npc_engine.api.schemas import QuestObjectiveBody
from npc_engine.config import Settings
from npc_engine.engines.quest.models import QuestObjectiveInput, QuestTransitionMeta
from npc_engine.utils.errors import QuestTransitionError


IDEMPOTENCY_REQUEST_HASH_HEADER = "X-Idempotency-Request-Hash"


def quest_error_status(error: QuestTransitionError) -> int:
    """Map QuestTransitionError codes to HTTP status codes.

    Args:
        error: QuestTransitionError with a machine-readable code.

    Returns:
        HTTP status code for the error.
    """
    status_code = 500
    if error.code == "QUEST_PROVENANCE_REQUIRED":
        status_code = 400
    if error.code in {"QUEST_REWARD_SOURCE_INVALID", "QUEST_REWARD_SOURCE_INSUFFICIENT"}:
        status_code = 400
    if error.code == "QUEST_NOT_FOUND":
        status_code = 404
    if error.code in {"QUEST_TRANSITION_INVALID", "QUEST_OBJECTIVE_UNKNOWN"}:
        status_code = 409
    if error.code == "QUEST_EVENT_SESSION_INVALID":
        status_code = 500
    return status_code


def quest_error_to_http(error: QuestTransitionError) -> HTTPException:
    """Convert a QuestTransitionError to a FastAPI HTTPException.

    Args:
        error: QuestTransitionError with code and detail.

    Returns:
        HTTPException with mapped status code and canonical error envelope.
    """
    return HTTPException(
        status_code=quest_error_status(error),
        detail=error_response(error_code=error.code, message=error.detail),
    )


def build_transition_meta(
    *,
    request: Request,
    settings: Settings,
    actor_id: str,
    reason: str,
) -> QuestTransitionMeta:
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


def to_objective_inputs(items: list[QuestObjectiveBody]) -> list[QuestObjectiveInput]:
    """Convert API objective body dtos to engine input models.

    Args:
        items: List of QuestObjectiveBody from the API request.

    Returns:
        List of QuestObjectiveInput for the quest lifecycle engine.
    """
    return [
        QuestObjectiveInput(
            objective_id=item.objective_id,
            target_count=item.target_count,
            objective_type=item.objective_type,
            target_id=item.target_id,
        )
        for item in items
    ]
