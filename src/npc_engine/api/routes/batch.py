"""
batch.py - Bulk routes for explicit gossip and event tick execution.
Layer: api
Purpose: (auto-detected — review)

Does NOT: advance game clock automatically.

Dependencies injected: GossipHandler, EventHandler, AsyncSession.
"""

from typing import Any

from fastapi import APIRouter, Depends
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session, get_event_handler, get_gossip_handler
from npc_engine.api.route_helpers import OkEnvelope, ok_response
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


@router.post("/batch/gossip_tick", response_model=OkEnvelope[dict[str, Any]])
async def run_gossip_tick(
    request: GossipTickRequest,
    session: AsyncSession = Depends(get_db_session),
    gossip_handler: GossipHandler = Depends(get_gossip_handler),
) -> dict[str, Any]:
    """Execute one explicit gossip tick."""

    tick_id = request.tick_override
    result = await gossip_handler.run_tick(
        session=session,
        tick_id=tick_id,
        max_pairs=request.max_pairs,
        npc_ids=request.npc_ids,
    )
    return ok_response(result)


@router.post("/batch/event_tick", response_model=OkEnvelope[dict[str, Any]])
async def run_event_tick(
    request: EventTickRequest,
    session: AsyncSession = Depends(get_db_session),
    event_handler: EventHandler = Depends(get_event_handler),
) -> dict[str, Any]:
    """Execute one explicit event tick."""

    tick_id = request.tick_override
    result = await event_handler.run_tick(session=session, tick_id=tick_id, location_ids=request.location_ids)
    return ok_response(result)
