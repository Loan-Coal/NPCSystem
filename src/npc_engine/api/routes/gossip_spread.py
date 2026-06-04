"""
Module: gossip_spread
Layer: api
Purpose: Route for player-planted rumor injection into the gossip propagation pipeline.
         POST /gossip/spread injects a fabricated belief at a target NPC; the gossip engine
         naturally propagates and distorts it to other NPCs on the next clock advance.
Does NOT: perform distortion or select gossip pairs.
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import ok_response
from npc_engine.graph.gossip_spread_service import inject_rumor_belief

_MAX_RUMOR_TEXT_LEN = 500
_MIN_SEVERITY = 0
_MAX_SEVERITY = 100
_DEFAULT_SEVERITY = 60

router = APIRouter(prefix="/gossip", tags=["gossip"])


class SpreadRumorRequest(BaseModel):
    """Request body for planting a fabricated rumor at a target NPC."""

    target_npc_id: str = Field(..., min_length=1)
    rumor_text: str = Field(..., min_length=1, max_length=_MAX_RUMOR_TEXT_LEN)
    severity: int = Field(default=_DEFAULT_SEVERITY, ge=_MIN_SEVERITY, le=_MAX_SEVERITY)
    tick_id: int = Field(..., ge=0)

    model_config = ConfigDict(frozen=True)


@router.post("/spread")
async def spread_rumor_route(
    body: SpreadRumorRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Inject a player-planted lie into a target NPC's KNOWS_ABOUT graph.

    The NPC immediately acquires the rumor as a KNOWS_ABOUT edge with
    knowledge_state='rumor'.  On the next clock advance, the gossip engine
    propagates and distorts it to co-located NPCs via the normal pair-selection
    pipeline.

    Args:
        body: target_npc_id, rumor_text, severity (0â€“100), and current tick_id.

    Returns:
        Envelope with event_id and npc_id.
    """
    event_id = await inject_rumor_belief(
        session,
        target_npc_id=body.target_npc_id,
        rumor_text=body.rumor_text,
        severity=body.severity,
        tick_id=body.tick_id,
    )
    return ok_response({"event_id": event_id, "npc_id": body.target_npc_id})
