"""
clock.py - Clock state and manual tick advancement routes.
Layer: api
Purpose: Clock state and manual tick advancement routes.

Does NOT: define gossip or event domain logic.

Dependencies injected: TickScheduler, AsyncSession.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session, get_tick_scheduler
from npc_engine.api.dependency_singletons import get_memory_engine
from npc_engine.api.route_helpers import OkEnvelope, error_response, ok_response
from npc_engine.config import MAX_DELTA_TICKS, Settings, get_settings
from npc_engine.scheduler.tick_scheduler import TickScheduler
from npc_engine.graph.world_state_reader import get_world_state
from npc_engine.world.world_time_service import _VALID_FIELDS, advance_time
from npc_engine.graph.world_state_writer import upsert_world_state
from npc_engine.utils.logging import get_logger

logger = get_logger(__name__)

_VALID_TIME_FIELDS = _VALID_FIELDS


class ClockAdvanceRequest(BaseModel):
    """Request payload for game-driven clock advancement."""

    delta_ticks: int = Field(default=1, ge=1, le=MAX_DELTA_TICKS)
    game_time_seconds: int = Field(default=1, ge=0)
    advance_time_field: str | None = Field(default=None)

    model_config = ConfigDict(frozen=True)


router = APIRouter()


# SEV-16: kept as dict[str, Any] by decision (DEC-114). The advance result merges
# the scheduler's dynamic tick-result dict with an optional world_state — a
# heterogeneous engine aggregate; a fixed model would 500 on shape drift.
@router.post("/clock/advance", response_model=OkEnvelope[dict[str, Any]])
async def advance_clock(
    request: ClockAdvanceRequest,
    session: AsyncSession = Depends(get_db_session),
    scheduler: TickScheduler = Depends(get_tick_scheduler),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
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
    if request.delta_ticks > settings.MAX_DELTA_TICKS:
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

    try:
        result = await scheduler.advance(
            session=session,
            tick_delta=request.delta_ticks,
            time_delta_seconds=request.game_time_seconds,
        )

        updated_world = None
        if request.advance_time_field is not None:
            current_world = await get_world_state(session, world_id=settings.WORLD_ID)
            advanced = advance_time(request.advance_time_field, current_world)
            updated_world = await upsert_world_state(session, advanced)
            if request.advance_time_field == "day":
                await get_memory_engine().decay_vividness()

        payload: dict[str, Any] = result
        if updated_world is not None:
            payload = {**payload, "world_state": updated_world.model_dump()}
        return ok_response(payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("clock_advance_failed", extra={"error": type(exc).__name__})
        raise HTTPException(
            status_code=500,
            detail=error_response(
                error_code="INTERNAL_ERROR",
                message="An internal error occurred.",
            ),
        ) from exc


# SEV-16: kept as dict[str, Any] by decision (DEC-114). State merges the scheduler
# state dump + runtime keys + a per-engine engine_status dict — heterogeneous aggregate.
@router.get("/clock/state", response_model=OkEnvelope[dict[str, Any]])
async def clock_state(scheduler: TickScheduler = Depends(get_tick_scheduler)) -> dict[str, Any]:
    """Return current clock snapshot with per-engine status.

    Includes ``engine_status`` â€” a dict mapping engine name to its last-run
    tick id and last error. Used by the S6.0 observability dashboard.
    """
    payload = scheduler.state.model_dump()
    payload["next_gossip_tick"] = scheduler.next_gossip_tick
    payload["next_event_tick"] = scheduler.next_event_tick
    payload["engine_status"] = scheduler.engine_status
    return ok_response(payload)
