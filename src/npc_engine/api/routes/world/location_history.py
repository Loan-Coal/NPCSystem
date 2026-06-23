"""
Module: location_history
Layer: api
Purpose: Admin HTTP routes for querying character location history (WAS_AT edges).
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.location_history_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, Query

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.graph.location_history_service import (
    get_alibi_window_svc,
    get_location_history_svc,
    prune_location_history,
)

router = APIRouter(prefix="/location-history", tags=["location-history"])


@router.get("/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def list_location_history(
    character_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return recent WAS_AT edges for a character in reverse chronological order.

    Args:
        character_id: ID of the character node.
        limit: Maximum number of history records to return (default 20).

    Returns:
        Envelope with list of location history dicts.
    """
    history = await get_location_history_svc(
        session, character_id=character_id, limit=limit
    )
    return ok_response({"history": history})


@router.get("/alibi/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def get_alibi(
    character_id: str,
    from_tick: int = Query(..., ge=0),
    to_tick: int = Query(..., ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return all locations a character occupied during a tick window.

    Args:
        character_id: ID of the character node.
        from_tick: Start of the tick window (inclusive).
        to_tick: End of the tick window (inclusive).

    Returns:
        Envelope with list of location records covering the window.
    """
    records = await get_alibi_window_svc(
        session,
        character_id=character_id,
        from_tick=from_tick,
        to_tick=to_tick,
    )
    return ok_response({"alibi": records})


@router.delete("/{character_id}/prune", response_model=OkEnvelope[dict[str, Any]])
async def prune_history(
    character_id: str,
    older_than_ticks: int = Query(..., ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Delete WAS_AT edges older than a tick threshold for a character.

    Args:
        character_id: ID of the character whose history to prune.
        older_than_ticks: Delete edges with departed_at_tick < this value.

    Returns:
        Envelope with count of deleted edges.
    """
    deleted = await prune_location_history(
        session, character_id=character_id, older_than_ticks=older_than_ticks
    )
    return ok_response({"deleted": deleted})
