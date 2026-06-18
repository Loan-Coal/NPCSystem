"""
Module: beliefs
Layer: api
Purpose: Admin HTTP routes for seeding and retrieving Belief nodes on characters.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.belief_service, api.dependencies.get_db_session
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
from npc_engine.graph.belief_service import (
    create_belief,
    delete_belief,
    get_beliefs_for_character_svc,
    update_confidence,
)
from npc_engine.world.time_utils import TimePoint

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateBeliefRequest(BaseModel):
    """Request body for seeding a belief on a character."""

    content: str = Field(..., min_length=1, max_length=512)
    confidence: int = Field(..., ge=0, le=100)
    game_time: dict[str, Any] = Field(
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


class UpdateConfidenceRequest(BaseModel):
    """Request body for updating belief confidence."""

    confidence: int = Field(..., ge=0, le=100)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class BeliefsPayload(BaseModel):
    """Typed payload for GET /beliefs/{character_id} (SEV-16).

    The ``beliefs`` group is fixed; individual rows are heterogeneous graph
    records, so each stays ``dict[str, Any]``.
    """

    beliefs: list[dict[str, Any]]

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/beliefs", tags=["beliefs"])


@router.post("/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def seed_belief(
    character_id: str,
    body: CreateBeliefRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Seed a new belief on a character.

    Args:
        character_id: ID of the character to attach the belief to.
        body: Belief content, confidence level, and optional game-time.

    Returns:
        Envelope with the new belief_id.
    """
    gt = body.game_time
    game_time = TimePoint(
        year=int(gt.get("year", 1)),
        season=str(gt.get("season", "spring")),
        day=int(gt.get("day", 1)),
        time_of_day=str(gt.get("time_of_day", "morning")),
    )
    belief_id = await create_belief(
        session,
        character_id=character_id,
        content=body.content,
        confidence=body.confidence,
        game_time=game_time,
        node_id=body.id,
    )
    return ok_response({"belief_id": belief_id})


@router.get("/{character_id}", response_model=OkEnvelope[BeliefsPayload])
async def list_beliefs(
    character_id: str,
    k: int = 10,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List beliefs for a character ordered by confidence descending.

    Args:
        character_id: ID of the character.
        k: Maximum number of beliefs to return (default 10).

    Returns:
        Envelope with list of belief dicts.
    """
    beliefs = await get_beliefs_for_character_svc(session, character_id=character_id, k=k)
    return ok_response(BeliefsPayload(beliefs=beliefs).model_dump())


@router.patch("/{belief_id}/confidence", response_model=OkEnvelope[dict[str, Any]])
async def patch_confidence(
    belief_id: str,
    body: UpdateConfidenceRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Update the confidence of an existing belief.

    Args:
        belief_id: ID of the Belief node.
        body: New confidence value (0â€“100).

    Returns:
        Envelope with updated belief_id.
    """
    await update_confidence(session, belief_id=belief_id, new_confidence=body.confidence)
    return ok_response({"belief_id": belief_id})


@router.delete("/{belief_id}", response_model=OkEnvelope[dict[str, Any]])
async def remove_belief(
    belief_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Hard-delete a single Belief node.

    Args:
        belief_id: ID of the Belief node to delete.

    Returns:
        Envelope confirming deletion.
    """
    await delete_belief(session, belief_id=belief_id)
    return ok_response({"belief_id": belief_id})
