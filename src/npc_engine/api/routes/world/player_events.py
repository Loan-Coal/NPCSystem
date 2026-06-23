"""
Module: player_events
Layer: api
Purpose: GET route returning recent player-observable events from the knowledge graph.
Does NOT: write to Neo4j, call LLMs, or bypass authentication middleware.
Dependencies: graph.event_queries.get_recent_player_events, api.dependencies.get_db_session.
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.api.router_registry (_register_public_routers).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.helpers import OkEnvelope, ok_response
from npc_engine.graph.event_queries import get_recent_player_events

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LIMIT_DEFAULT = 20
_LIMIT_MAX = 100

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class PlayerEventRow(BaseModel):
    """A single player-observable event record."""

    event_id: str
    event_type: str
    label: str
    severity: int | None
    tick_id: int
    location_id: str
    src_character_id: str

    model_config = ConfigDict(frozen=True)


class PlayerEventsData(BaseModel):
    """Payload returned by GET /player/{player_id}/events."""

    events: list[PlayerEventRow]

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/player", tags=["player_events"])


@router.get("/{player_id}/events", response_model=OkEnvelope[PlayerEventsData])
async def list_player_events(
    player_id: str,
    limit: int = Query(default=_LIMIT_DEFAULT, ge=1, le=_LIMIT_MAX),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return the most recent events observable by the given player.

    Queries Event nodes reachable from the player's KNOWS_ABOUT edges,
    ordered by tick descending.

    Args:
        player_id: ID of the player Character node.
        limit: Maximum number of events to return (default 20, max 100).
        session: Active Neo4j async session (injected by FastAPI).

    Returns:
        Envelope with a ``events`` list of PlayerEventRow records.
        Returns 200 with an empty list when no events are known.
    """
    rows = await get_recent_player_events(session, player_id=player_id, limit=limit)
    events = [PlayerEventRow(**row) for row in rows]
    return ok_response({"events": [e.model_dump() for e in events]})
