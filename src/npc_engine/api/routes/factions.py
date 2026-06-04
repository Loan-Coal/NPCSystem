"""
Module: factions
Layer: api
Purpose: Admin HTTP routes for Faction node CRUD and relationship management.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies injected: FactionService (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_faction_service
from npc_engine.api.route_helpers import graph_error_to_http, ok_response, require_node
from npc_engine.graph.faction_service import FactionService
from npc_engine.utils.errors import FactionMembershipError, FactionNotFoundError

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

FactionArchetype = Literal["religious", "political", "mercantile", "military", "criminal", "social", "other"]
MemberRole = Literal["leader", "officer", "member", "recruit"]
MemberStatus = Literal["active", "exiled", "deceased"]

# ---------------------------------------------------------------------------
# Request / internal models
# ---------------------------------------------------------------------------


class CreateFactionRequest(BaseModel):
    """Request body for faction creation."""

    id: str
    name: str
    description: Annotated[str | None, Field(max_length=500)] = None
    archetype: FactionArchetype
    is_active: bool = True

    model_config = ConfigDict(frozen=True)


class AddMemberRequest(BaseModel):
    """Request body for adding a character to a faction."""

    character_id: str
    role: MemberRole
    status: MemberStatus

    model_config = ConfigDict(frozen=True)


class SetStandingRequest(BaseModel):
    """Request body for setting faction standing toward another faction."""

    standing: Annotated[int, Field(ge=-100, le=100)]

    model_config = ConfigDict(frozen=True)


class _FactionNode(BaseModel):
    """Internal Pydantic model passed to faction_writer.upsert_faction."""

    id: str
    name: str
    description: str | None
    archetype: str
    is_active: bool
    created_at: str
    last_graph_updated_at: str

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/factions", tags=["factions"])


@router.post("/", status_code=201)
async def create_faction(
    request: CreateFactionRequest,
    service: FactionService = Depends(get_faction_service),
) -> dict[str, Any]:
    """Create or update a Faction node."""
    now = datetime.now(timezone.utc).isoformat()
    node = _FactionNode(
        id=request.id,
        name=request.name,
        description=request.description,
        archetype=request.archetype,
        is_active=request.is_active,
        created_at=now,
        last_graph_updated_at=now,
    )
    await service.upsert_faction(node)
    return ok_response({"id": request.id})


@router.get("/")
async def list_factions(
    is_active: bool | None = None,
    service: FactionService = Depends(get_faction_service),
) -> dict[str, Any]:
    """List all factions, optionally filtered by active status."""
    factions = await service.list_factions(is_active=is_active)
    return ok_response(factions)


@router.get("/{faction_id}")
async def get_faction(
    faction_id: str,
    service: FactionService = Depends(get_faction_service),
) -> dict[str, Any]:
    """Fetch a single Faction node by ID."""
    faction = await service.get_faction(faction_id)
    return ok_response(require_node(faction, node_type="Faction"))


@router.post("/{faction_id}/members", status_code=201)
async def add_member(
    faction_id: str,
    request: AddMemberRequest,
    service: FactionService = Depends(get_faction_service),
) -> dict[str, Any]:
    """Add a character as a member of a faction."""
    try:
        await service.add_member(
            character_id=request.character_id,
            faction_id=faction_id,
            role=request.role,
            status=request.status,
        )
    except FactionMembershipError as error:
        raise graph_error_to_http(error) from error
    return ok_response({"character_id": request.character_id, "faction_id": faction_id})


@router.get("/{faction_id}/members")
async def list_members(
    faction_id: str,
    service: FactionService = Depends(get_faction_service),
) -> dict[str, Any]:
    """List all active members of a faction."""
    members = await service.get_members_of_faction(faction_id)
    return ok_response(members)


@router.delete("/{faction_id}/members/{character_id}")
async def remove_member(
    faction_id: str,
    character_id: str,
    service: FactionService = Depends(get_faction_service),
) -> dict[str, Any]:
    """Remove a character from a faction."""
    try:
        await service.remove_member(character_id=character_id, faction_id=faction_id)
    except FactionMembershipError as error:
        raise graph_error_to_http(error) from error
    return ok_response({"character_id": character_id, "faction_id": faction_id})


@router.put("/{faction_id}/standings/{target_id}")
async def set_standing(
    faction_id: str,
    target_id: str,
    request: SetStandingRequest,
    service: FactionService = Depends(get_faction_service),
) -> dict[str, Any]:
    """Set directed standing from one faction toward another."""
    try:
        await service.set_standing(src_id=faction_id, dst_id=target_id, standing=request.standing)
    except FactionNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response({"src_id": faction_id, "dst_id": target_id, "standing": request.standing})


@router.get("/{faction_id}/standings")
async def list_standings(
    faction_id: str,
    service: FactionService = Depends(get_faction_service),
) -> dict[str, Any]:
    """List all directed standings from a faction toward others."""
    standings = await service.list_standings(faction_id)
    return ok_response(standings)


@router.post("/{faction_id}/controls/{location_id}", status_code=201)
async def set_controls(
    faction_id: str,
    location_id: str,
    service: FactionService = Depends(get_faction_service),
) -> dict[str, Any]:
    """Declare that a faction controls a location."""
    try:
        await service.set_controls(faction_id=faction_id, location_id=location_id)
    except FactionNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response({"faction_id": faction_id, "location_id": location_id})


@router.delete("/{faction_id}/controls/{location_id}")
async def remove_controls(
    faction_id: str,
    location_id: str,
    service: FactionService = Depends(get_faction_service),
) -> dict[str, Any]:
    """Remove a faction's control over a location."""
    try:
        await service.remove_controls(faction_id=faction_id, location_id=location_id)
    except FactionNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response({"faction_id": faction_id, "location_id": location_id})
