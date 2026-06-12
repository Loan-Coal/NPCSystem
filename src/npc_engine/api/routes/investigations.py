"""
Module: investigations
Layer: api
Purpose: Read-only HTTP route for surfacing investigation context (evidence, witnesses,
         suspects, deductions, alibi contradictions, rumor contradictions) for a given
         investigator and crime event (Phase H0.3).
Does NOT: write to the graph or call LLMs.
Dependencies: engines.investigation.investigation_engine (via dependencies_advanced),
              api.dependencies.get_db_session, api.route_helpers.
Dependencies injected: AsyncSession (via FastAPI Depends), InvestigationEngine (via Depends).
Used by: npc_engine.api.router_registry (registered at API_V1_PREFIX).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncSession

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.dependencies_advanced import get_investigation_engine
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.engines.investigation.investigation_engine import InvestigationEngine

router = APIRouter(prefix="/investigations", tags=["investigations"])


def _has_investigation_data(context: dict[str, Any]) -> bool:
    """True when the context holds any evidence, witnesses, or suspects (else → 404)."""
    return bool(context.get("evidence") or context.get("witnesses") or context.get("suspects"))


@router.get(
    "/{investigator_id}/{event_id}",
    response_model=OkEnvelope[dict[str, Any]],
)
async def get_investigation_context(
    investigator_id: str,
    event_id: str,
    session: AsyncSession = Depends(get_db_session),
    engine: InvestigationEngine = Depends(get_investigation_engine),
) -> dict[str, Any]:
    """Return aggregated investigation context for a crime event.

    Delegates to InvestigationEngine.get_investigation_context which runs six
    parallel graph queries (evidence, witnesses, suspects, deductions, alibi
    windows, contradicting rumors) and surfaces structural inconsistencies.

    Args:
        investigator_id: ID of the Character conducting the investigation.
        event_id: ID of the Event (crime) being investigated.
        session: Scoped Neo4j session injected by FastAPI.
        engine: Singleton InvestigationEngine injected by FastAPI.

    Returns:
        JSON envelope with evidence, witnesses, suspects, deductions,
        alibi_contradictions, and rumor_contradictions lists.

    Raises:
        HTTPException 404: When event_id resolves to an empty evidence + witnesses
            set (i.e. the event does not exist or has no associated data).
    """
    context = await engine.get_investigation_context(
        session, investigator_id=investigator_id, event_id=event_id,
    )
    if not _has_investigation_data(context):
        raise HTTPException(status_code=404, detail=f"No investigation data found for event {event_id!r}")
    return ok_response(context)
