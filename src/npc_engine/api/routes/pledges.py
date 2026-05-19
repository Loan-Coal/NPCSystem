"""
Module: pledges
Layer: api
Purpose: HTTP routes for creating, listing, and breaking character pledges.
Does NOT: perform authentication or implement oath engine logic.
Dependencies: graph.pledge_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main
"""

from __future__ import annotations

from typing import Literal

from neo4j import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import ok_response
from npc_engine.graph.pledge_service import (
    break_pledge,
    create_pledge,
    get_pledges_for_character_svc,
)

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


PLEDGE_TYPES = Literal["protect", "serve", "kill", "marry", "mentor", "fealty", "vendetta"]


class CreatePledgeRequest(BaseModel):
    """Request body for creating a pledge between characters."""

    pledgee_id: str = Field(..., min_length=1)
    pledge_type: PLEDGE_TYPES
    tick: int = Field(..., ge=0)
    expires_at_tick: int | None = Field(default=None, ge=0)
    witness_id: str | None = Field(default=None)
    binding_event_id: str | None = Field(default=None)
    severity: int = Field(default=50, ge=0, le=100)

    model_config = ConfigDict(frozen=True)


class BreakPledgeRequest(BaseModel):
    """Request body for breaking an active pledge."""

    pledgee_id: str = Field(..., min_length=1)
    pledge_type: PLEDGE_TYPES
    tick: int = Field(..., ge=0)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/pledges", tags=["pledges"])


@router.post("/characters/{character_id}")
async def create_character_pledge(
    character_id: str,
    body: CreatePledgeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create a new PLEDGE edge from a character to another.

    Args:
        character_id: ID of the pledger (character making the pledge).
        body: Pledge details including pledgee, type, and optional expiry.

    Returns:
        Envelope confirming the pledge was created.
    """
    await create_pledge(
        session,
        pledger_id=character_id,
        pledgee_id=body.pledgee_id,
        pledge_type=body.pledge_type,
        tick=body.tick,
        expires_at_tick=body.expires_at_tick,
        witness_id=body.witness_id,
        binding_event_id=body.binding_event_id,
        severity=body.severity,
    )
    return ok_response({"pledger_id": character_id, "pledgee_id": body.pledgee_id, "pledge_type": body.pledge_type})


@router.get("/characters/{character_id}")
async def list_character_pledges(
    character_id: str,
    active_only: bool = True,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List pledges where character is the pledger.

    Args:
        character_id: ID of the character.
        active_only: When True (default), return only active pledges.

    Returns:
        Envelope with list of pledge dicts.
    """
    pledges = await get_pledges_for_character_svc(session, character_id, active_only=active_only)
    return ok_response({"pledges": pledges})


@router.post("/characters/{character_id}/break")
async def break_character_pledge(
    character_id: str,
    body: BreakPledgeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Break an active pledge and apply relationship consequences.

    Args:
        character_id: ID of the pledger breaking the pledge.
        body: Pledgee ID, pledge type, and current tick.

    Returns:
        Envelope confirming the pledge was broken.
    """
    await break_pledge(
        session,
        pledger_id=character_id,
        pledgee_id=body.pledgee_id,
        pledge_type=body.pledge_type,
        tick=body.tick,
    )
    return ok_response({
        "pledger_id": character_id,
        "pledgee_id": body.pledgee_id,
        "pledge_type": body.pledge_type,
        "broken": True,
    })
