"""
action.py - Endpoint to report player actions against NPCs.

Does NOT: execute world tick logic.

Dependencies injected: AsyncSession, Settings.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from neo4j import AsyncSession

from api.dependencies import get_db_session
from api.schemas import ActionReportRequest
from config import Settings, get_settings
from graph.graph_writer import apply_relation_delta
from utils.errors import RelationEdgeNotFoundError


router = APIRouter()


@router.post("/action")
async def report_action(
    request: ActionReportRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Apply a conservative relation delta for a reported gameplay action."""

    delta = min(15, max(-15, request.intensity // 10))
    deltas = {"trust": 0, "fear": 0, "affection": 0}
    if request.action_type == "help":
        deltas = {"trust": delta, "fear": -delta, "affection": delta}
    if request.action_type == "attack":
        deltas = {"trust": -delta, "fear": delta, "affection": -delta}
    if request.action_type == "give_item":
        deltas = {"trust": delta, "fear": 0, "affection": delta}
    if request.action_type == "steal":
        deltas = {"trust": -delta, "fear": delta, "affection": -delta}
    if request.action_type == "observe":
        deltas = {"trust": 0, "fear": 0, "affection": 0}
    try:
        await apply_relation_delta(
            session=session,
            settings=settings,
            src_id=request.npc_id,
            dst_id=request.player_id,
            deltas=deltas,
            cause_id=f"action:{request.action_type}",
            tick_id=int(datetime.now(timezone.utc).timestamp()),
        )
    except RelationEdgeNotFoundError:
        return {"status": "ignored", "reason": "relation_missing"}
    return {"status": "ok", "applied_deltas": deltas}
