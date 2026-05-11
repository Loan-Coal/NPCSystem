"""
clock.py - Clock state and manual tick advancement routes.

Does NOT: define gossip or event domain logic.

Dependencies injected: TickScheduler, AsyncSession.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session, get_tick_scheduler
from npc_engine.api.route_helpers import error_response, ok_response
from npc_engine.config import Settings, get_settings
from npc_engine.scheduler.tick_scheduler import TickScheduler
from npc_engine.world.world_reader import get_world_state
from npc_engine.world.world_time_service import _VALID_FIELDS, advance_time
from npc_engine.world.world_writer import upsert_world_state

_VALID_TIME_FIELDS = _VALID_FIELDS


class ClockAdvanceRequest(BaseModel):
    """Request payload for game-driven clock advancement."""

    delta_ticks: int = Field(default=1, ge=1, le=200)
    game_time_seconds: int = Field(default=1, ge=0)
    advance_time_field: str | None = Field(default=None)

    model_config = ConfigDict(frozen=True)


router = APIRouter()


@router.post("/clock/advance")
async def advance_clock(
    request: ClockAdvanceRequest,
    session: AsyncSession = Depends(get_db_session),
    scheduler: TickScheduler = Depends(get_tick_scheduler),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Advance clock and trigger due engine ticks.

    When advance_time_field is provided, also advances that structured time
    field on WorldState and persists the result.
    """
    if settings.CLOCK_MODE != "game_driven":
        raise HTTPException(
            status_code=400,
            detail=error_response(
                error_code="CLOCK_MODE_INVALID",
                message="Clock can only be advanced in game_driven mode",
            ),
        )
    if request.delta_ticks > settings.MAX_CONCURRENT_TICKS * 10:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                error_code="CLOCK_DELTA_OUT_OF_BOUNDS",
                message="delta_ticks exceeds allowed bound",
            ),
        )
    if request.advance_time_field is not None and request.advance_time_field not in _VALID_TIME_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                error_code="INVALID_TIME_FIELD",
                message=f"advance_time_field must be one of {sorted(_VALID_TIME_FIELDS)}",
            ),
        )

    result = await scheduler.advance(
        session=session,
        tick_delta=request.delta_ticks,
        time_delta_seconds=request.game_time_seconds,
    )

    updated_world = None
    if request.advance_time_field is not None:
        current_world = await get_world_state(session)
        advanced = advance_time(request.advance_time_field, current_world)
        updated_world = await upsert_world_state(session, advanced)

    payload: dict[str, Any] = cast(dict[str, Any], result)
    if updated_world is not None:
        payload = {**payload, "world_state": updated_world.model_dump()}
    return ok_response(payload)


@router.get("/clock/state")
async def clock_state(scheduler: TickScheduler = Depends(get_tick_scheduler)) -> dict:
    """Return current clock snapshot."""

    payload = cast(dict[str, Any], scheduler.state.model_dump())
    payload["next_gossip_tick"] = scheduler.next_gossip_tick
    payload["next_event_tick"] = scheduler.next_event_tick
    return ok_response(payload)
