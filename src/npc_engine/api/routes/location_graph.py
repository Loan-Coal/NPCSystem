"""
Module: location_graph
Layer: api
Purpose: Admin HTTP routes for CONNECTS_TO edge management and shortest-path queries.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.location_graph_queries, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import ok_response
from npc_engine.graph.location_graph_queries import (
    create_connection,
    delete_connection,
    get_connections_for_location,
    get_shortest_path,
)

router = APIRouter(prefix="/locations", tags=["location-graph"])

_VALID_KINDS = frozenset({"road", "river", "sea", "secret"})


class ConnectLocationRequest(BaseModel):
    """Request body for creating a bidirectional CONNECTS_TO edge."""

    kind: str = Field(..., description="Connection type: road | river | sea | secret")
    travel_cost: int = Field(..., ge=1, description="Ticks to traverse this edge (min 1)")
    is_open: bool = Field(default=True, description="Whether the connection is passable")


@router.post("/{from_id}/connects/{to_id}", status_code=201)
async def connect_locations(
    from_id: str,
    to_id: str,
    body: ConnectLocationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a bidirectional CONNECTS_TO edge between two locations.

    Both Aâ†’B and Bâ†’A edges are created with the same cost and kind.
    Idempotent â€” calling again with the same kind updates travel_cost and is_open.

    Args:
        from_id: ID of the source location node.
        to_id: ID of the destination location node.
        body: Connection parameters.

    Returns:
        Envelope confirming the created connection.

    Raises:
        422: If kind is not one of road | river | sea | secret.
        422: If from_id equals to_id.
    """
    if body.kind not in _VALID_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {sorted(_VALID_KINDS)}")
    if from_id == to_id:
        raise HTTPException(status_code=422, detail="Cannot connect a location to itself")
    await create_connection(
        session,
        from_id=from_id,
        to_id=to_id,
        kind=body.kind,
        travel_cost=body.travel_cost,
        is_open=body.is_open,
    )
    return ok_response(
        {
            "from_id": from_id,
            "to_id": to_id,
            "kind": body.kind,
            "travel_cost": body.travel_cost,
            "is_open": body.is_open,
        }
    )


@router.get("/{location_id}/connections")
async def list_connections(
    location_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return all outbound CONNECTS_TO edges from a location, ordered by travel cost.

    Args:
        location_id: ID of the source location.

    Returns:
        Envelope with list of connection dicts.
    """
    connections = await get_connections_for_location(session, location_id=location_id)
    return ok_response({"connections": connections})


@router.get("/{from_id}/path/{to_id}")
async def shortest_path(
    from_id: str,
    to_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return the shortest path between two locations by hop count.

    Args:
        from_id: Starting location ID.
        to_id: Destination location ID.

    Returns:
        Envelope with path data (node_ids, hops, total_cost).

    Raises:
        404: If no path exists between the two locations.
    """
    path = await get_shortest_path(session, from_location_id=from_id, to_location_id=to_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"No path from {from_id!r} to {to_id!r}")
    return ok_response(path)


@router.delete("/{from_id}/connects/{to_id}", status_code=200)
async def remove_connection(
    from_id: str,
    to_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Remove the bidirectional CONNECTS_TO edges between two locations.

    Args:
        from_id: ID of one endpoint location.
        to_id: ID of the other endpoint location.

    Returns:
        Envelope confirming deletion.
    """
    await delete_connection(session, from_id=from_id, to_id=to_id)
    return ok_response({"from_id": from_id, "to_id": to_id, "deleted": True})
