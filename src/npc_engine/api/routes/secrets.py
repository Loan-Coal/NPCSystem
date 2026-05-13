"""
Module: secrets
Layer: api
Purpose: Admin HTTP routes for creating and retrieving Secret nodes on characters.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.secret_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from neo4j import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import ok_response
from npc_engine.graph.secret_service import (
    create_secret,
    delete_secret,
    get_secrets_for_character_svc,
)
from npc_engine.world.time_utils import TimePoint

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateSecretRequest(BaseModel):
    """Request body for creating a secret on a character."""

    content: str = Field(..., min_length=1, max_length=512)
    severity: int = Field(..., ge=0, le=100)
    game_time: dict = Field(
        default_factory=lambda: {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
    )

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/secrets", tags=["secrets"])


@router.post("/{character_id}")
async def create_secret_for_character(
    character_id: str,
    body: CreateSecretRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create a secret and link it to a character.

    Args:
        character_id: ID of the character who initially knows the secret.
        body: Secret content, severity, and game-time snapshot.

    Returns:
        Envelope with the new secret_id.
    """
    gt = body.game_time
    game_time = TimePoint(
        year=int(gt.get("year", 1)),
        season=str(gt.get("season", "spring")),
        day=int(gt.get("day", 1)),
        time_of_day=str(gt.get("time_of_day", "morning")),
    )
    secret_id = await create_secret(
        session,
        character_id=character_id,
        content=body.content,
        severity=body.severity,
        game_time=game_time,
    )
    return ok_response({"secret_id": secret_id})


@router.get("/{character_id}")
async def list_secrets_for_character(
    character_id: str,
    k: int = 3,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List secrets known by a character, ordered by severity descending.

    Args:
        character_id: ID of the character.
        k: Maximum number of secrets to return (default 3).

    Returns:
        Envelope with list of secret dicts.
    """
    secrets = await get_secrets_for_character_svc(session, character_id=character_id, k=k)
    return ok_response({"secrets": secrets})


@router.delete("/{secret_id}")
async def remove_secret(
    secret_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Hard-delete a single Secret node.

    Args:
        secret_id: ID of the Secret node to delete.

    Returns:
        Envelope confirming deletion.
    """
    await delete_secret(session, secret_id=secret_id)
    return ok_response({"secret_id": secret_id})
