"""
Module: witnessed
Layer: api
Purpose: Admin HTTP routes for querying WITNESSED edges (character observation records).
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.witnessed_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, Query

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import ok_response
from npc_engine.graph.witnessed_service import (
    get_witnessed_by_svc,
    get_witnesses_of_event_svc,
    mark_disclosed,
)

router = APIRouter(prefix="/witnessed", tags=["witnessed"])


@router.get("/event/{event_id}")
async def get_event_witnesses(
    event_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return all characters who witnessed a given event.

    Args:
        event_id: ID of the Event node.

    Returns:
        Envelope with list of witness records.
    """
    witnesses = await get_witnesses_of_event_svc(session, event_id=event_id)
    return ok_response({"witnesses": witnesses})


@router.get("/by/{subject_id}")
async def get_observations_of_subject(
    subject_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return all WITNESSED edges pointing at a subject character.

    Args:
        subject_id: ID of the character being observed.
        limit: Maximum number of records to return (default 20).

    Returns:
        Envelope with list of witness records ordered by most recent first.
    """
    observations = await get_witnessed_by_svc(session, subject_id=subject_id, limit=limit)
    return ok_response({"observations": observations})


@router.patch("/disclose")
async def disclose_witness(
    witness_id: str = Query(...),
    subject_id: str = Query(...),
    event_id: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Mark a WITNESSED edge as disclosed (the witness has shared the information).

    Args:
        witness_id: ID of the witness character.
        subject_id: ID of the subject character.
        event_id: ID of the event the edge relates to.

    Returns:
        Envelope confirming the disclosure.
    """
    await mark_disclosed(
        session,
        witness_id=witness_id,
        subject_id=subject_id,
        event_id=event_id,
    )
    return ok_response({"disclosed": True})
