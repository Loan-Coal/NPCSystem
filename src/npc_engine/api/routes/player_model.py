"""
Module: player_model
Layer: api
Purpose: HTTP route for reading an NPC's model of the player (perceived_trust,
         perceived_intent) — the PlayerModel nodes the scheduler updates per tick (F1.4/F2.2).
Does NOT: execute Cypher directly; delegates to graph.player_model_writer.get_player_model.
Dependencies injected: AsyncSession via FastAPI Depends.
Used by: npc_engine.api.router_registry (registered at API_V1_PREFIX).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.graph.player_model_writer import get_player_model


class PlayerModelResponse(BaseModel):
    """Typed response payload for the NPC player-model endpoint."""

    npc_id: str
    player_id: str
    perceived_trust: int | None = None
    perceived_intent: str | None = None
    last_updated_at: str | None = None

    model_config = ConfigDict(frozen=True)


router = APIRouter(prefix="/npc", tags=["player_model"])


@router.get("/{npc_id}/player-model/{player_id}", response_model=OkEnvelope[PlayerModelResponse])
async def get_npc_player_model(
    npc_id: str,
    player_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return the NPC's model of the player (perceived trust + intent).

    Args:
        npc_id: ID of the NPC whose model is requested.
        player_id: ID of the player being modelled.
        session: Scoped Neo4j session injected by FastAPI.

    Returns:
        JSON envelope with npc_id, player_id, perceived_trust, perceived_intent,
        and last_updated_at.

    Raises:
        HTTPException 404: If the NPC has no PlayerModel for the player.
    """
    record = await get_player_model(session, npc_id=npc_id, player_id=player_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"no player model {npc_id} -> {player_id}")

    payload = PlayerModelResponse(
        npc_id=record.npc_id,
        player_id=record.player_id,
        perceived_trust=record.perceived_trust,
        perceived_intent=record.perceived_intent,
        last_updated_at=record.last_updated_at,
    )
    return ok_response(payload.model_dump())
