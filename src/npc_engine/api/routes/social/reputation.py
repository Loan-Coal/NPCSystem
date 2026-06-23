"""
Module: reputation
Layer: api
Purpose: HTTP routes for reading and writing character reputation with factions.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies injected: ReputationService (via FastAPI Depends).
Used by: npc_engine.main (graph_router at API_V1_PREFIX, admin_router at admin_prefix)
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_reputation_service
from npc_engine.api.helpers import OkEnvelope, graph_error_to_http, ok_response, require_node
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
    """Request body for applying a relative reputation delta.

    When location_id and tick_id are both provided, a reputation_change Event
    node is created at the given location and KNOWS_ABOUT edges are seeded for
    co-located NPCs, so the standing change enters the gossip pipeline.
    """

    delta: Annotated[int, Field(ge=-200, le=200)]
    location_id: str | None = None
    tick_id: int | None = None

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Response models (SEV-16)
# ---------------------------------------------------------------------------


class ReputationRow(BaseModel):
    """A HAS_REPUTATION_WITH edge row from GET /graph/characters/{id}/reputation.

    Extra graph props are preserved verbatim (extra='allow') so the wire shape is
    unchanged while OpenAPI gets a named component.
    """

    faction_id: str
    standing: int

    model_config = ConfigDict(extra="allow")


class ReputationStandingPayload(BaseModel):
    """Typed payload for the reputation set/adjust writes — the resulting standing."""

    character_id: str
    faction_id: str
    standing: int

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Read router  (registered at API_V1_PREFIX â†’ /v1/graph/characters/...)
# ---------------------------------------------------------------------------

graph_router = APIRouter(prefix="/graph/characters", tags=["reputation"])


@graph_router.get("/{character_id}/reputation", response_model=OkEnvelope[list[ReputationRow]])
async def list_reputations(
    character_id: str,
    service: ReputationService = Depends(get_reputation_service),
) -> dict[str, Any]:
    """List all faction reputation edges for a character."""
    reputations = await service.list_reputations(character_id=character_id)
    return ok_response(reputations)


@graph_router.get("/{character_id}/reputation/{faction_id}", response_model=OkEnvelope[dict[str, Any]])
async def get_reputation(
    character_id: str,
    faction_id: str,
    service: ReputationService = Depends(get_reputation_service),
) -> dict[str, Any]:
    """Fetch a character's reputation with a specific faction."""
    reputation = await service.get_reputation(character_id=character_id, faction_id=faction_id)
    return ok_response(require_node(reputation, node_type="Reputation"))


# ---------------------------------------------------------------------------
# Write router  (registered at admin_prefix â†’ /v1/admin/characters/...)
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/characters", tags=["reputation"])


@admin_router.put("/{character_id}/reputation/{faction_id}", status_code=200, response_model=OkEnvelope[ReputationStandingPayload])
async def set_reputation(
    character_id: str,
    faction_id: str,
    request: SetReputationRequest,
    service: ReputationService = Depends(get_reputation_service),
) -> dict[str, Any]:
    """Set a character's absolute reputation standing with a faction."""
    try:
        await service.set_reputation(
            character_id=character_id,
            faction_id=faction_id,
            standing=request.standing,
        )
    except ReputationNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response(
        ReputationStandingPayload(
            character_id=character_id, faction_id=faction_id, standing=request.standing
        ).model_dump()
    )


@admin_router.post("/{character_id}/reputation/{faction_id}/adjust", status_code=200, response_model=OkEnvelope[ReputationStandingPayload])
async def adjust_reputation(
    character_id: str,
    faction_id: str,
    request: AdjustReputationRequest,
    service: ReputationService = Depends(get_reputation_service),
) -> dict[str, Any]:
    """Apply a delta to a character's reputation with a faction (clamped to [-100, 100]).

    When location_id and tick_id are provided, also creates a reputation_change
    Event node and seeds KNOWS_ABOUT edges for co-located NPCs.
    """
    try:
        if request.location_id is not None and request.tick_id is not None:
            new_standing = await service.adjust_reputation_with_event(
                character_id=character_id,
                faction_id=faction_id,
                delta=request.delta,
                location_id=request.location_id,
                tick_id=request.tick_id,
            )
        else:
            new_standing = await service.adjust_reputation(
                character_id=character_id,
                faction_id=faction_id,
                delta=request.delta,
            )
    except ReputationNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response(
        ReputationStandingPayload(
            character_id=character_id, faction_id=faction_id, standing=new_standing
        ).model_dump()
    )
