"""
batch.py - Bulk routes for explicit gossip and event tick execution.
Layer: api
Purpose: Exposes POST endpoints for directly triggering one gossip or event tick
         outside the clock advance loop (useful for testing and tooling).
Does NOT: advance game clock automatically, open graph sessions.
Dependencies injected: GossipHandler, EventHandler (via FastAPI Depends).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_event_handler, get_gossip_handler
from npc_engine.api.helpers import OkEnvelope, ok_response
from npc_engine.engines.events.event_handler import EventHandler
from npc_engine.engines.gossip.gossip_handler import GossipHandler


class GossipTickRequest(BaseModel):
    """Request payload for direct gossip tick execution."""

    npc_ids: list[str] = Field(default_factory=list)
    tick_override: int = Field(ge=0)
    max_pairs: int = Field(default=20, ge=1, le=500)

    model_config = ConfigDict(frozen=True)


class EventTickRequest(BaseModel):
    """Request payload for direct event tick execution."""

    location_ids: list[str] = Field(default_factory=list)
    tick_override: int = Field(ge=0)

    model_config = ConfigDict(frozen=True)


router = APIRouter()


# SEV-16: kept as dict[str, Any] by decision (DEC-114). Returns the handler's
# run_tick() result — a dynamic engine-aggregate dict, not a fixed shape.
@router.post("/batch/gossip_tick", response_model=OkEnvelope[dict[str, Any]])
async def run_gossip_tick(
    request: GossipTickRequest,
    gossip_handler: GossipHandler = Depends(get_gossip_handler),
) -> dict[str, Any]:
    """Execute one explicit gossip tick."""

    tick_id = request.tick_override
    result = await gossip_handler.run_tick(
        tick_id=tick_id,
        max_pairs=request.max_pairs,
        npc_ids=request.npc_ids,
    )
    return ok_response(result)


# SEV-16: kept as dict[str, Any] by decision (DEC-114) — dynamic run_tick() aggregate.
@router.post("/batch/event_tick", response_model=OkEnvelope[dict[str, Any]])
async def run_event_tick(
    request: EventTickRequest,
    event_handler: EventHandler = Depends(get_event_handler),
) -> dict[str, Any]:
    """Execute one explicit event tick."""

    tick_id = request.tick_override
    result = await event_handler.run_tick(tick_id=tick_id, location_ids=request.location_ids)
    return ok_response(result)
