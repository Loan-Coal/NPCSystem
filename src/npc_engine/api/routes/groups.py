"""
Module: groups
Layer: api
Purpose: Admin HTTP routes for creating, querying, and dissolving Group nodes and memberships.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.group_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import error_response, ok_response
from npc_engine.graph.group_service import (
    add_member,
    create_group,
    dissolve_group,
    get_groups_for_character_svc,
    get_members_svc,
)
from npc_engine.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateGroupRequest(BaseModel):
    """Request body for creating a new Group node."""

    name: str = Field(..., min_length=1, max_length=256)
    kind: str = Field(..., pattern=r"^(clique|conspiracy|family|crew|fellowship|mob)$")
    cohesion: int = Field(..., ge=0, le=100)
    is_secret: bool = Field(default=False)
    formed_at_tick: int = Field(..., ge=0)
    home_location_id: str | None = Field(default=None)

    model_config = ConfigDict(frozen=True)


class AddMemberRequest(BaseModel):
    """Request body for adding a character to a group."""

    character_id: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1, max_length=64)
    joined_at_tick: int = Field(..., ge=0)
    commitment: int = Field(..., ge=0, le=100)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("")
async def create_group_route(
    body: CreateGroupRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create a new Group node.

    Args:
        body: Group name, kind, cohesion, secrecy flag, formation tick, and optional home location.

    Returns:
        Envelope with the new group_id.
    """
    group_id = await create_group(
        session,
        name=body.name,
        kind=body.kind,
        cohesion=body.cohesion,
        is_secret=body.is_secret,
        formed_at_tick=body.formed_at_tick,
        home_location_id=body.home_location_id,
    )
    return ok_response({"group_id": group_id})


@router.get("/{character_id}")
async def list_groups_for_character(
    character_id: str,
    include_dissolved: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List groups a character belongs to.

    Args:
        character_id: ID of the character.
        include_dissolved: When true, also returns dissolved groups.

    Returns:
        Envelope with list of group membership dicts.
    """
    groups = await get_groups_for_character_svc(
        session, character_id=character_id, include_dissolved=include_dissolved
    )
    return ok_response({"groups": groups})


@router.get("/members/{group_id}")
async def list_group_members(
    group_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List active members of a group.

    Args:
        group_id: ID of the Group node.

    Returns:
        Envelope with list of member dicts.
    """
    members = await get_members_svc(session, group_id=group_id)
    return ok_response({"members": members})


@router.post("/{group_id}/members")
async def add_member_to_group(
    group_id: str,
    body: AddMemberRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Add a character to an existing group.

    Args:
        group_id: ID of the Group node.
        body: Character ID, role, join tick, and commitment level.

    Returns:
        Envelope confirming membership.
    """
    try:
        await add_member(
            session,
            group_id=group_id,
            character_id=body.character_id,
            role=body.role,
            joined_at_tick=body.joined_at_tick,
            commitment=body.commitment,
        )
    except Exception as exc:
        logger.warning("group_add_member_failed", extra={"error": type(exc).__name__})
        raise HTTPException(
            status_code=422,
            detail=error_response(
                error_code="INVALID_REQUEST", message="Invalid request parameter."
            ),
        ) from exc
    return ok_response({"group_id": group_id, "character_id": body.character_id})


@router.delete("/{group_id}")
async def dissolve_group_route(
    group_id: str,
    tick: int,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Mark a group as dissolved at the given tick.

    Args:
        group_id: ID of the Group node.
        tick: Game tick at which the group dissolved.

    Returns:
        Envelope confirming dissolution.
    """
    await dissolve_group(session, group_id=group_id, tick=tick)
    return ok_response({"group_id": group_id, "dissolved_at_tick": tick})
