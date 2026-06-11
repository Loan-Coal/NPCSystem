"""
Module: locations
Layer: api
Purpose: HTTP routes for Location node hierarchy — PART_OF containment edges
         (admin write) and ancestor/descendant read queries.
Does NOT: perform authentication or validate auth scopes directly. Does NOT
         handle CONNECTS_TO edges (those live in location_graph.py).
Dependencies: graph.location_writer, graph.location_graph_queries,
              api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix for writes, api_v1 for reads)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.graph.location_graph_queries import get_ancestors, get_descendants
from npc_engine.graph.location_writer import delete_part_of, write_part_of

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreatePartOfRequest(BaseModel):
    """Request body for creating a PART_OF containment edge."""

    parent_id: str = Field(..., min_length=1, description="ID of the parent Location node.")
    hierarchy_level: int = Field(
        ...,
        ge=0,
        le=4,
        description="Depth level: 0=venue, 1=district, 2=city, 3=region, 4=world.",
    )

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Routers — admin writes and read queries registered separately in main.py
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/locations", tags=["location-hierarchy-admin"])
read_router = APIRouter(prefix="/locations", tags=["location-hierarchy"])


# ---------------------------------------------------------------------------
# Admin write routes
# ---------------------------------------------------------------------------


@admin_router.post("/{child_id}/part_of", response_model=OkEnvelope[dict[str, Any]])
async def create_part_of(
    child_id: str,
    body: CreatePartOfRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create or update a PART_OF containment edge from child to parent.

    Uses MERGE — calling this endpoint multiple times with the same
    (child_id, parent_id) pair is idempotent.

    Args:
        child_id: ID of the child Location node (the contained location).
        body: parent_id and hierarchy_level.

    Returns:
        Envelope confirming the edge was written.

    Raises:
        HTTPException 400: If child_id equals parent_id.
    """
    try:
        await write_part_of(
            session,
            child_id=child_id,
            parent_id=body.parent_id,
            hierarchy_level=body.hierarchy_level,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok_response({"child_id": child_id, "parent_id": body.parent_id})


@admin_router.delete("/{child_id}/part_of/{parent_id}", response_model=OkEnvelope[dict[str, Any]])
async def remove_part_of(
    child_id: str,
    parent_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Remove a PART_OF containment edge between two Location nodes.

    Safe to call when the edge does not exist — returns 200 either way.

    Args:
        child_id: ID of the child Location node.
        parent_id: ID of the parent Location node.

    Returns:
        Envelope confirming the deletion was requested.
    """
    await delete_part_of(session, child_id=child_id, parent_id=parent_id)
    return ok_response({"child_id": child_id, "parent_id": parent_id})


# ---------------------------------------------------------------------------
# Read routes
# ---------------------------------------------------------------------------


@read_router.get("/{location_id}/ancestors", response_model=OkEnvelope[dict[str, Any]])
async def list_ancestors(
    location_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return an ordered list of ancestor location IDs from parent to root.

    Args:
        location_id: ID of the Location node whose ancestors to retrieve.

    Returns:
        Envelope with list of ancestor location IDs (immediate parent first).
    """
    ancestors = await get_ancestors(session, location_id=location_id)
    return ok_response({"location_id": location_id, "ancestors": ancestors})


@read_router.get("/{location_id}/descendants", response_model=OkEnvelope[dict[str, Any]])
async def list_descendants(
    location_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return a flat list of all descendant location IDs.

    Args:
        location_id: ID of the Location node whose descendants to retrieve.

    Returns:
        Envelope with flat list of descendant location IDs.
    """
    descendants = await get_descendants(session, location_id=location_id)
    return ok_response({"location_id": location_id, "descendants": descendants})
