"""
Module: investigations
Layer: api
Purpose: Read-only HTTP route for surfacing investigation context (evidence, witnesses,
         suspects, deductions, alibi contradictions, rumor contradictions) for a given
         investigator and crime event (Phase H0.3).
Does NOT: write to the graph or call LLMs.
Dependencies: engines.investigation.investigation_engine (via dependencies_advanced),
              api.route_helpers.
Dependencies injected: InvestigationEngine (via Depends; it holds its own graph port).
Used by: npc_engine.api.router_registry (registered at API_V1_PREFIX).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from npc_engine.api.dependencies_advanced import get_investigation_engine
from npc_engine.api.helpers import OkEnvelope, ok_response
from npc_engine.engines.investigation.investigation_engine import InvestigationEngine

router = APIRouter(prefix="/investigations", tags=["investigations"])


class InvestigationPayload(BaseModel):
    """Typed response payload for GET /investigations/{investigator}/{event} (SEV-16).

    The six top-level groups are fixed; individual rows remain heterogeneous graph
    query results, so each list stays ``dict[str, Any]``.
    """

    evidence: list[dict[str, Any]]
    witnesses: list[dict[str, Any]]
    suspects: list[dict[str, Any]]
    deductions: list[dict[str, Any]]
    alibi_contradictions: list[dict[str, Any]]
    rumor_contradictions: list[dict[str, Any]]

    model_config = ConfigDict(frozen=True)


def _has_investigation_data(context: dict[str, Any]) -> bool:
    """True when the context holds any evidence, witnesses, or suspects (else → 404)."""
    return bool(context.get("evidence") or context.get("witnesses") or context.get("suspects"))


@router.get(
    "/{investigator_id}/{event_id}",
    response_model=OkEnvelope[InvestigationPayload],
)
async def get_investigation_context(
    investigator_id: str,
    event_id: str,
    engine: InvestigationEngine = Depends(get_investigation_engine),
) -> dict[str, Any]:
    """Return aggregated investigation context for a crime event.

    Delegates to InvestigationEngine.get_investigation_context which runs six
    parallel graph queries (evidence, witnesses, suspects, deductions, alibi
    windows, contradicting rumors) and surfaces structural inconsistencies.

    Args:
        investigator_id: ID of the Character conducting the investigation.
        event_id: ID of the Event (crime) being investigated.
        engine: Singleton InvestigationEngine injected by FastAPI.

    Returns:
        JSON envelope with evidence, witnesses, suspects, deductions,
        alibi_contradictions, and rumor_contradictions lists.

    Raises:
        HTTPException 404: When event_id resolves to an empty evidence + witnesses
            set (i.e. the event does not exist or has no associated data).
    """
    context = await engine.get_investigation_context(
        investigator_id=investigator_id, event_id=event_id,
    )
    if not _has_investigation_data(context):
        raise HTTPException(status_code=404, detail=f"No investigation data found for event {event_id!r}")
    return ok_response(InvestigationPayload(**context).model_dump())
