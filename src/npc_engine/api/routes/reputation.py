"""
Module: reputation
Layer: api
Purpose: HTTP routes for reading and writing character reputation with factions.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies injected: ReputationService (via FastAPI Depends).
Used by: npc_engine.main (graph_router at API_V1_PREFIX, admin_router at admin_prefix)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_reputation_service
from npc_engine.api.route_helpers import graph_error_to_http, ok_response, require_node
from npc_engine.graph.reputation_service import ReputationService
from npc_engine.utils.errors import ReputationNotFoundError

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SetReputationRequest(BaseModel):
    """Request body for setting absolute reputation standing."""

    standing: Annotated[int, Field(ge=-100, le=100)]

    model_config = ConfigDict(frozen=True)


class AdjustReputationRequest(BaseModel):
    """Request body for applying a relative reputation delta."""

    delta: Annotated[int, Field(ge=-200, le=200)]

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Read router  (registered at API_V1_PREFIX → /v1/graph/characters/...)
# ---------------------------------------------------------------------------

graph_router = APIRouter(prefix="/graph/characters", tags=["reputation"])


@graph_router.get("/{character_id}/reputation")
async def list_reputations(
    character_id: str,
    service: ReputationService = Depends(get_reputation_service),
) -> dict:
    """List all faction reputation edges for a character."""
    reputations = await service.list_reputations(character_id=character_id)
    return ok_response(reputations)  # type: ignore[no-any-return]


@graph_router.get("/{character_id}/reputation/{faction_id}")
async def get_reputation(
    character_id: str,
    faction_id: str,
    service: ReputationService = Depends(get_reputation_service),
) -> dict:
    """Fetch a character's reputation with a specific faction."""
    reputation = await service.get_reputation(character_id=character_id, faction_id=faction_id)
    return ok_response(require_node(reputation, node_type="Reputation"))  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Write router  (registered at admin_prefix → /v1/admin/characters/...)
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/characters", tags=["reputation"])


@admin_router.put("/{character_id}/reputation/{faction_id}", status_code=200)
async def set_reputation(
    character_id: str,
    faction_id: str,
    request: SetReputationRequest,
    service: ReputationService = Depends(get_reputation_service),
) -> dict:
    """Set a character's absolute reputation standing with a faction."""
    try:
        await service.set_reputation(
            character_id=character_id,
            faction_id=faction_id,
            standing=request.standing,
        )
    except ReputationNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response({"character_id": character_id, "faction_id": faction_id, "standing": request.standing})  # type: ignore[no-any-return]


@admin_router.post("/{character_id}/reputation/{faction_id}/adjust", status_code=200)
async def adjust_reputation(
    character_id: str,
    faction_id: str,
    request: AdjustReputationRequest,
    service: ReputationService = Depends(get_reputation_service),
) -> dict:
    """Apply a delta to a character's reputation with a faction (clamped to [-100, 100])."""
    try:
        new_standing = await service.adjust_reputation(
            character_id=character_id,
            faction_id=faction_id,
            delta=request.delta,
        )
    except ReputationNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response({"character_id": character_id, "faction_id": faction_id, "standing": new_standing})  # type: ignore[no-any-return]
