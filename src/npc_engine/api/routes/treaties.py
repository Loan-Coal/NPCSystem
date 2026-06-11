"""
Module: treaties
Layer: api
Purpose: HTTP routes for creating, listing, expiring, and breaking treaties.
Does NOT: perform authentication or implement treaty engine logic.
Dependencies: graph.treaty_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.graph.treaty_service import (
    TreatyCondition,
    break_treaty,
    create_treaty,
    expire_treaty,
    get_active_treaties_svc,
)

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTreatyRequest(BaseModel):
    """Request body for creating a treaty between factions."""

    parties: list[str] = Field(..., min_length=2)
    terms_narrative: str = Field(..., min_length=1)
    terms_conditions: list[TreatyCondition] = Field(default_factory=list)
    signed_at_tick: int = Field(..., ge=0)
    expires_at_tick: int | None = Field(default=None, ge=0)
    binding_event_id: str | None = Field(default=None)

    model_config = ConfigDict(frozen=True)


class ExpireTreatyRequest(BaseModel):
    """Request body for manually expiring a treaty."""

    tick: int = Field(..., ge=0)

    model_config = ConfigDict(frozen=True)


class BreakTreatyRequest(BaseModel):
    """Request body for breaking a treaty."""

    breaking_faction_id: str = Field(..., min_length=1)
    tick: int = Field(..., ge=0)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/treaties", tags=["treaties"])


@router.post("/", response_model=OkEnvelope[dict[str, Any]])
async def create_treaty_route(
    body: CreateTreatyRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a new Treaty and BOUND_BY edges for each signatory faction.

    Args:
        body: Treaty details including parties, terms, and optional expiry.

    Returns:
        Envelope with the new treaty_id.
    """
    treaty_id = await create_treaty(
        session,
        parties=body.parties,
        terms_narrative=body.terms_narrative,
        terms_conditions=list(body.terms_conditions),
        signed_at_tick=body.signed_at_tick,
        expires_at_tick=body.expires_at_tick,
        binding_event_id=body.binding_event_id,
    )
    return ok_response({"treaty_id": treaty_id})


@router.get("/factions/{faction_id}", response_model=OkEnvelope[dict[str, Any]])
async def list_faction_treaties(
    faction_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List active treaties for a faction.

    Args:
        faction_id: ID of the Faction node.

    Returns:
        Envelope with list of treaty dicts.
    """
    treaties = await get_active_treaties_svc(session, faction_id)
    return ok_response({"treaties": treaties})


@router.post("/{treaty_id}/expire", response_model=OkEnvelope[dict[str, Any]])
async def expire_treaty_route(
    treaty_id: str,
    body: ExpireTreatyRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Manually expire a treaty.

    Args:
        treaty_id: ID of the Treaty node.
        body: Current tick.

    Returns:
        Envelope confirming expiry.
    """
    await expire_treaty(session, treaty_id, body.tick)
    return ok_response({"treaty_id": treaty_id, "status": "expired"})


@router.post("/{treaty_id}/break", response_model=OkEnvelope[dict[str, Any]])
async def break_treaty_route(
    treaty_id: str,
    body: BreakTreatyRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Break a treaty.

    Args:
        treaty_id: ID of the Treaty node.
        body: Breaking faction ID and current tick.

    Returns:
        Envelope confirming the treaty was broken.
    """
    await break_treaty(
        session,
        treaty_id=treaty_id,
        breaking_faction_id=body.breaking_faction_id,
        tick=body.tick,
    )
    return ok_response({"treaty_id": treaty_id, "status": "broken", "broken_by": body.breaking_faction_id})
