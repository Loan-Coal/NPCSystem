"""
clock.py - Clock state and manual tick advancement routes.

Does NOT: define gossip or event domain logic.

Dependencies injected: TickScheduler, AsyncSession.
"""

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, cast

from api.dependencies import get_db_session, get_tick_scheduler
from config import Settings, get_settings
from scheduler.tick_scheduler import TickScheduler


class ClockAdvanceRequest(BaseModel):
    """Request payload for game-driven clock advancement."""

    delta_ticks: int = Field(default=1, ge=1, le=200)
    game_time_seconds: int = Field(default=1, ge=0)

    model_config = ConfigDict(frozen=True)


router = APIRouter()


@router.post("/clock/advance")
async def advance_clock(
    request: ClockAdvanceRequest,
    session: AsyncSession = Depends(get_db_session),
    scheduler: TickScheduler = Depends(get_tick_scheduler),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Advance clock and trigger due engine ticks."""

    if settings.CLOCK_MODE != "game_driven":
        raise HTTPException(status_code=400, detail="Clock can only be advanced in game_driven mode")
    if request.delta_ticks > settings.MAX_CONCURRENT_TICKS * 10:
        raise HTTPException(status_code=400, detail="delta_ticks exceeds allowed bound")

    return await scheduler.advance(
        session=session,
        tick_delta=request.delta_ticks,
        time_delta_seconds=request.game_time_seconds,
    )


@router.get("/clock/state")
async def clock_state(scheduler: TickScheduler = Depends(get_tick_scheduler)) -> dict:
    """Return current clock snapshot."""

    payload = cast(dict[str, Any], scheduler.state.model_dump())
    payload["next_gossip_tick"] = scheduler.next_gossip_tick
    payload["next_event_tick"] = scheduler.next_event_tick
    return payload
