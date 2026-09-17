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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_event_handler, get_gossip_handler
from npc_engine.api.helpers import OkEnvelope, ok_response
from npc_engine.engines.events.event_handler import EventHandler
from npc_engine.engines.gossip.gossip_handler import GossipHandler
from npc_engine.api.dependency_singletons import get_game_clock
from npc_engine.api.helpers import resolve_tick
from npc_engine.engines.ports.clock_port import ClockPort
from npc_engine.utils.errors import EventTemplateNotFoundError
from npc_engine.utils.logging import get_logger

logger = get_logger(__name__)

# Bounds on a caller-named event template id (pool ids look like "evt_21_iron_legion_advance").
TEMPLATE_ID_MAX_LENGTH: int = 64


class GossipTickRequest(BaseModel):
    """Request payload for direct gossip tick execution."""

    npc_ids: list[str] = Field(default_factory=list)
    tick_override: int | None = Field(default=None, ge=0)
    max_pairs: int = Field(default=20, ge=1, le=500)

    model_config = ConfigDict(frozen=True)


class EventTickRequest(BaseModel):
    """Request payload for direct event tick execution."""

    location_ids: list[str] = Field(default_factory=list)
    tick_override: int | None = Field(default=None, ge=0)
    template_id: str | None = Field(default=None, min_length=1, max_length=TEMPLATE_ID_MAX_LENGTH)

    model_config = ConfigDict(frozen=True)


router = APIRouter()


# SEV-16: kept as dict[str, Any] by decision (DEC-114). Returns the handler's
# run_tick() result — a dynamic engine-aggregate dict, not a fixed shape.
@router.post("/batch/gossip_tick", response_model=OkEnvelope[dict[str, Any]])
async def run_gossip_tick(
    request: GossipTickRequest,
    gossip_handler: GossipHandler = Depends(get_gossip_handler),
    clock: ClockPort = Depends(get_game_clock),
) -> dict[str, Any]:
    """Execute one explicit gossip tick."""

    tick_id = resolve_tick(request.tick_override, clock)
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
    clock: ClockPort = Depends(get_game_clock),
) -> dict[str, Any]:
    """Execute one explicit event tick, optionally forcing a named pool template."""

    tick_id = resolve_tick(request.tick_override, clock)
    try:
        result = await event_handler.run_tick(
            tick_id=tick_id, location_ids=request.location_ids, template_id=request.template_id
        )
    except EventTemplateNotFoundError as error:
        logger.info("event_tick_unknown_template", extra={"error": str(error)})
        raise HTTPException(status_code=422, detail="Unknown event template") from error
    return ok_response(result)
