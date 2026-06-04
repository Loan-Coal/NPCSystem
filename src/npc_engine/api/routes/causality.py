"""
Module: causality
Layer: api
Purpose: Admin HTTP routes for querying CAUSED_BY provenance chains.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.causality_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, Query

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import ok_response
from npc_engine.graph.causality_service import (
    get_causes_svc,
    get_consequence_chain_svc,
)

router = APIRouter(prefix="/causality", tags=["causality"])


@router.get("/chain/{event_id}")
async def get_consequence_chain(
    event_id: str,
    max_depth: int = Query(default=5, ge=1, le=20),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return the causal consequence chain starting from an event.

    Args:
        event_id: ID of the root Event node to start traversal from.
        max_depth: Maximum hops to traverse (default 5, max 20).

    Returns:
        Envelope with ordered list of effect nodes and their causation metadata.
    """
    chain = await get_consequence_chain_svc(
        session, root_event_id=event_id, max_depth=max_depth
    )
    return ok_response({"chain": chain})


@router.get("/causes/{node_id}")
async def get_direct_causes(
    node_id: str,
    node_type: str = Query(default="Event"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return direct cause events for a given node.

    Args:
        node_id: ID of the effect node (Event, Quest, or Rumor).
        node_type: Label of the effect node (default "Event").

    Returns:
        Envelope with list of cause event dicts.
    """
    causes = await get_causes_svc(session, node_id=node_id, node_type=node_type)
    return ok_response({"causes": causes})
