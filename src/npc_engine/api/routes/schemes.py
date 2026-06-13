"""
Module: schemes
Layer: api
Purpose: HTTP route for reading an NPC's active/discovered schemes and their covert
         steps — the SchemeAdvanceTick/SchemeDetectionTick state (F1.6 → F2.3).
Does NOT: execute Cypher directly; delegates to graph.scheme_reader.
Dependencies injected: AsyncSession via FastAPI Depends.
Used by: npc_engine.api.router_registry (registered at API_V1_PREFIX).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from neo4j import AsyncSession
from pydantic import BaseModel

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.graph.scheme_reader import SchemeWithSteps, get_schemes_with_steps_for_npc

router = APIRouter(prefix="/npc", tags=["schemes"])


class SchemesPayload(BaseModel):
    """Typed response payload for GET /npc/{id}/schemes (SEV-03 L3-15).

    Attributes:
        npc_id: The queried NPC's ID.
        schemes: All schemes (any status) with their ordered covert steps.
    """

    npc_id: str
    schemes: list[SchemeWithSteps]


@router.get("/{npc_id}/schemes", response_model=OkEnvelope[SchemesPayload])
async def get_npc_schemes(
    npc_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return the NPC's schemes (active + discovered) with their covert steps.

    Args:
        npc_id: ID of the scheming NPC.
        session: Scoped Neo4j session injected by FastAPI.

    Returns:
        JSON envelope wrapping SchemesPayload with ``npc_id`` and ``schemes`` —
        a list of objects each carrying scheme_id, goal, status, discovered, and
        an ordered steps list. Typed as OkEnvelope[SchemesPayload] so OpenAPI
        clients receive a real schema (SEV-03 L3-15).
    """
    schemes = await get_schemes_with_steps_for_npc(session, npc_id=npc_id)
    payload = SchemesPayload(npc_id=npc_id, schemes=schemes)
    return ok_response(payload.model_dump())
