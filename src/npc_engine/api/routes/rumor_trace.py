"""
Module: rumor_trace
Layer: api
Purpose: Routes for rumor tracing and correction.
         GET /gossip/trace/{event_id} returns the NPC chain that received a fabricated
         event; POST /gossip/correct marks one NPC's KNOWS_ABOUT edge as corrected so
         the lie is removed from their dialogue context.
Does NOT: perform distortion, select gossip pairs, or propagate beliefs.
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.graph.rumor_trace_service import correct_rumor_at_npc, trace_rumor_chain

router = APIRouter(prefix="/gossip", tags=["gossip"])

_MAX_EVENT_ID_LEN = 200
_MAX_NPC_ID_LEN = 200


class CorrectRumorRequest(BaseModel):
    """Request body for correcting a planted rumor at a specific NPC."""

    npc_id: str = Field(..., min_length=1, max_length=_MAX_NPC_ID_LEN)
    event_id: str = Field(..., min_length=1, max_length=_MAX_EVENT_ID_LEN)

    model_config = ConfigDict(frozen=True)


@router.get("/trace/{event_id}", response_model=OkEnvelope[dict[str, Any]])
async def trace_rumor_route(
    event_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return the ordered NPC chain that holds a KNOWS_ABOUT edge to event_id.

    The chain is ordered by learned_at_tick ascending (origin â†’ downstream).
    Corrected holders are excluded from the result so only active believers appear.

    Args:
        event_id: ID of the fabricated Event node to trace.

    Returns:
        Envelope with ``chain`` (list of NPC entries) and ``event_id``.
    """
    chain = await trace_rumor_chain(session, event_id)
    return ok_response({"event_id": event_id, "chain": chain})


@router.post("/correct", response_model=OkEnvelope[dict[str, Any]])
async def correct_rumor_route(
    body: CorrectRumorRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Mark one NPC's belief in a fabricated event as corrected.

    After this call, the NPC's KNOWS_ABOUT edge to the event has
    knowledge_state='corrected' and is excluded from their dialogue context.
    NPCs further downstream that have already received the rumor are unaffected.

    Args:
        body: npc_id and event_id identifying the edge to correct.

    Returns:
        Envelope with ``npc_id``, ``event_id``, and ``corrected`` (bool).

    Raises:
        HTTP 404 if no KNOWS_ABOUT edge exists between npc_id and event_id.
    """
    corrected = await correct_rumor_at_npc(session, body.npc_id, body.event_id)
    if not corrected:
        raise HTTPException(
            status_code=404,
            detail=f"No KNOWS_ABOUT edge from '{body.npc_id}' to event '{body.event_id}'",
        )
    return ok_response({"npc_id": body.npc_id, "event_id": body.event_id, "corrected": True})
