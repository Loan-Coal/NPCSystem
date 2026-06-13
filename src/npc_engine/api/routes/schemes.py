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

from typing import Any

from fastapi import APIRouter, Depends
from neo4j import AsyncSession

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.graph.scheme_reader import get_schemes_with_steps_for_npc

router = APIRouter(prefix="/npc", tags=["schemes"])


@router.get("/{npc_id}/schemes", response_model=OkEnvelope[dict[str, Any]])
async def get_npc_schemes(
    npc_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return the NPC's schemes (active + discovered) with their covert steps.

    Args:
        npc_id: ID of the scheming NPC.
        session: Scoped Neo4j session injected by FastAPI.

    Returns:
        JSON envelope with ``npc_id`` and ``schemes`` — a list of objects each
        carrying scheme_id, goal, status, discovered, and an ordered steps list.
    """
    schemes = await get_schemes_with_steps_for_npc(session, npc_id=npc_id)
    payload = {
        "npc_id": npc_id,
        "schemes": [scheme.model_dump() for scheme in schemes],
    }
    return ok_response(payload)
