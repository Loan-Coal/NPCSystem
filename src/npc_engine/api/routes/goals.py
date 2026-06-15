"""
Module: goals
Layer: api
Purpose: Admin HTTP routes for seeding, retrieving, and patching Goal nodes on characters.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.goal_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.graph.goal_service import (
    create_goal,
    delete_goal,
    get_goals_for_character_svc,
    update_goal_status,
)
from npc_engine.world.time_utils import TimePoint

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateGoalRequest(BaseModel):
    """Request body for seeding a goal on a character."""

    description: str = Field(..., min_length=1, max_length=512)
    urgency: int = Field(..., ge=0, le=100)
    target_id: str | None = Field(default=None)
    game_time: dict = Field(
        default_factory=lambda: {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
    )
    id: str | None = Field(
        default=None,
        description=(
            "Caller-supplied stable ID. When provided the node is merged (idempotent). "
            "When omitted a UUID is auto-generated."
        ),
    )

    model_config = ConfigDict(frozen=True)


class UpdateGoalStatusRequest(BaseModel):
    """Request body for updating goal status."""

    status: str = Field(..., pattern="^(active|achieved|abandoned)$")

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class GoalsPayload(BaseModel):
    """Typed payload for GET /goals/{character_id} (SEV-16).

    The ``goals`` group is fixed; individual rows are heterogeneous graph
    records, so each stays ``dict[str, Any]``.
    """

    goals: list[dict[str, Any]]

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def seed_goal(
    character_id: str,
    body: CreateGoalRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Seed a new goal on a character.

    Args:
        character_id: ID of the character to attach the goal to.
        body: Goal description, urgency, optional target_id, and game-time.

    Returns:
        Envelope with the new goal_id.
    """
    gt = body.game_time
    game_time = TimePoint(
        year=int(gt.get("year", 1)),
        season=str(gt.get("season", "spring")),
        day=int(gt.get("day", 1)),
        time_of_day=str(gt.get("time_of_day", "morning")),
    )
    goal_id = await create_goal(
        session,
        character_id=character_id,
        description=body.description,
        urgency=body.urgency,
        game_time=game_time,
        target_id=body.target_id,
        node_id=body.id,
    )
    return ok_response({"goal_id": goal_id})


@router.get("/{character_id}", response_model=OkEnvelope[GoalsPayload])
async def list_goals(
    character_id: str,
    k: int = 10,
    status: str = "active",
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List goals for a character ordered by urgency descending.

    Args:
        character_id: ID of the character.
        k: Maximum number of goals to return (default 10).
        status: Filter by status; pass empty string for all statuses.

    Returns:
        Envelope with list of goal dicts.
    """
    goals = await get_goals_for_character_svc(
        session, character_id=character_id, k=k, status_filter=status
    )
    return ok_response(GoalsPayload(goals=goals).model_dump())


@router.patch("/{goal_id}/status", response_model=OkEnvelope[dict[str, Any]])
async def patch_goal_status(
    goal_id: str,
    body: UpdateGoalStatusRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Update the status of an existing goal.

    Args:
        goal_id: ID of the Goal node.
        body: New status value (active, achieved, or abandoned).

    Returns:
        Envelope with updated goal_id.
    """
    await update_goal_status(session, goal_id=goal_id, new_status=body.status)
    return ok_response({"goal_id": goal_id})


@router.delete("/{goal_id}", response_model=OkEnvelope[dict[str, Any]])
async def remove_goal(
    goal_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Hard-delete a single Goal node.

    Args:
        goal_id: ID of the Goal node to delete.

    Returns:
        Envelope confirming deletion.
    """
    await delete_goal(session, goal_id=goal_id)
    return ok_response({"goal_id": goal_id})
