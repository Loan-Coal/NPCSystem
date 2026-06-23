"""
Module: schedules
Layer: api
Purpose: Admin HTTP routes for Schedule node CRUD and character assignment.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies injected: ScheduleService (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Annotated, Literal, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_schedule_service
from npc_engine.api.helpers import OkEnvelope, graph_error_to_http, ok_response, require_node
from npc_engine.graph.schedule_service import ScheduleService
from npc_engine.utils.errors import ScheduleAssignmentError, ScheduleNotFoundError

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

TimeOfDay = Literal["morning", "midday", "afternoon", "evening", "night"]

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ScheduleEntry(BaseModel):
    """A single time-slot entry in a schedule."""

    time_of_day: TimeOfDay
    location_id: str
    activity: str | None = None

    model_config = ConfigDict(frozen=True)


class CreateScheduleRequest(BaseModel):
    """Request body for schedule creation or update."""

    id: str
    name: str
    description: Annotated[str | None, Field(max_length=500)] = None
    entries: list[ScheduleEntry]

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.post("/", status_code=201, response_model=OkEnvelope[dict[str, Any]])
async def create_schedule(
    request: CreateScheduleRequest,
    service: ScheduleService = Depends(get_schedule_service),
) -> dict[str, Any]:
    """Create or update a Schedule node."""
    entries = [e.model_dump(exclude_none=True) for e in request.entries]
    schedule = await service.create_schedule(
        schedule_id=request.id,
        name=request.name,
        description=request.description,
        entries=entries,
    )
    return ok_response({"id": schedule["id"]})


@router.get("/{schedule_id}", response_model=OkEnvelope[dict[str, Any]])
async def get_schedule(
    schedule_id: str,
    service: ScheduleService = Depends(get_schedule_service),
) -> dict[str, Any]:
    """Fetch a single Schedule node by ID."""
    try:
        schedule = await service.get_schedule(schedule_id)
    except ScheduleNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response(schedule)


@router.post("/{schedule_id}/assign/{character_id}", status_code=201, response_model=OkEnvelope[dict[str, Any]])
async def assign_schedule(
    schedule_id: str,
    character_id: str,
    service: ScheduleService = Depends(get_schedule_service),
) -> dict[str, Any]:
    """Assign a schedule to a character, replacing any existing assignment."""
    try:
        await service.assign_schedule(character_id=character_id, schedule_id=schedule_id)
    except ScheduleAssignmentError as error:
        raise graph_error_to_http(error) from error
    return ok_response({"character_id": character_id, "schedule_id": schedule_id})


@router.delete("/{character_id}/unassign", response_model=OkEnvelope[dict[str, Any]])
async def unassign_schedule(
    character_id: str,
    service: ScheduleService = Depends(get_schedule_service),
) -> dict[str, Any]:
    """Remove a character's schedule assignment."""
    await service.unassign_schedule(character_id=character_id)
    return ok_response({"character_id": character_id})


@router.get("/character/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def get_character_schedule(
    character_id: str,
    service: ScheduleService = Depends(get_schedule_service),
) -> dict[str, Any]:
    """Fetch the schedule a character follows, if any."""
    schedule = await service.get_character_schedule(character_id)
    return ok_response(require_node(schedule, node_type="Schedule"))


@router.get("/character/{character_id}/at", response_model=OkEnvelope[dict[str, Any]])
async def get_character_location_at(
    character_id: str,
    time_of_day: TimeOfDay,
    service: ScheduleService = Depends(get_schedule_service),
) -> dict[str, Any]:
    """Return the location a character is scheduled to be at a given time of day."""
    location_id = await service.get_character_location_at(character_id, time_of_day)
    return ok_response({"character_id": character_id, "time_of_day": time_of_day, "location_id": location_id})


@router.get("/location/{location_id}/at", response_model=OkEnvelope[dict[str, Any]])
async def get_characters_at_location(
    location_id: str,
    time_of_day: TimeOfDay,
    service: ScheduleService = Depends(get_schedule_service),
) -> dict[str, Any]:
    """Return character IDs scheduled to be at a location at a given time of day."""
    character_ids = await service.get_characters_at_location(location_id, time_of_day)
    return ok_response({"location_id": location_id, "time_of_day": time_of_day, "character_ids": character_ids})
