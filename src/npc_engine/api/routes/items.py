"""
Module: items
Layer: api
Purpose: Admin HTTP routes for creating, retrieving, and transferring Item nodes.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.item_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.graph.item_service import (
    create_item,
    delete_item,
    get_items_for_character_svc,
    transfer_ownership,
)
from npc_engine.world.time_utils import TimePoint

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateItemRequest(BaseModel):
    """Request body for creating an item on a character."""

    name: str = Field(..., min_length=1, max_length=512)
    description: str = Field(..., min_length=1, max_length=512)
    value: int = Field(..., ge=0)
    rarity: str = Field(..., min_length=1, max_length=64)
    type: str = Field(..., min_length=1, max_length=64)
    is_unique: bool = Field(default=False)
    properties: dict[str, Any] | None = Field(default=None)
    game_time: dict[str, Any] = Field(
        default_factory=lambda: {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
    )

    model_config = ConfigDict(frozen=True)


class TransferOwnerRequest(BaseModel):
    """Request body for transferring item ownership to another character."""

    to_character_id: str = Field(..., min_length=1)
    game_time: dict[str, Any] = Field(
        default_factory=lambda: {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
    )

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ItemsPayload(BaseModel):
    """Typed payload for GET /items/{character_id} (SEV-16).

    The ``items`` group is fixed; individual rows are heterogeneous graph
    records, so each stays ``dict[str, Any]``.
    """

    items: list[dict[str, Any]]

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/items", tags=["items"])


@router.post("/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def create_item_for_character(
    character_id: str,
    body: CreateItemRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create an item and assign ownership to a character.

    Args:
        character_id: ID of the character who will own the item.
        body: Item fields and game-time snapshot.

    Returns:
        Envelope with the new item_id.
    """
    gt = body.game_time
    game_time = TimePoint(
        year=int(gt.get("year", 1)),
        season=str(gt.get("season", "spring")),
        day=int(gt.get("day", 1)),
        time_of_day=str(gt.get("time_of_day", "morning")),
    )
    item_id = await create_item(
        session,
        character_id=character_id,
        name=body.name,
        description=body.description,
        value=body.value,
        rarity=body.rarity,
        type_=body.type,
        is_unique=body.is_unique,
        game_time=game_time,
        properties=body.properties,
    )
    return ok_response({"item_id": item_id})


@router.get("/{character_id}", response_model=OkEnvelope[ItemsPayload])
async def list_items_for_character(
    character_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List all items owned by a character.

    Args:
        character_id: ID of the character.

    Returns:
        Envelope with list of item dicts.
    """
    items = await get_items_for_character_svc(session, character_id=character_id)
    return ok_response(ItemsPayload(items=items).model_dump())


@router.patch("/{item_id}/owner", response_model=OkEnvelope[dict[str, Any]])
async def patch_item_owner(
    item_id: str,
    body: TransferOwnerRequest,
    from_character_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Transfer ownership of an item to another character.

    Args:
        item_id: ID of the Item node.
        from_character_id: ID of the character currently owning the item (query param).
        body: Target character ID and game-time snapshot.

    Returns:
        Envelope with the item_id.
    """
    gt = body.game_time
    game_time = TimePoint(
        year=int(gt.get("year", 1)),
        season=str(gt.get("season", "spring")),
        day=int(gt.get("day", 1)),
        time_of_day=str(gt.get("time_of_day", "morning")),
    )
    await transfer_ownership(
        session,
        item_id=item_id,
        from_character_id=from_character_id,
        to_character_id=body.to_character_id,
        game_time=game_time,
    )
    return ok_response({"item_id": item_id})


@router.delete("/{item_id}", response_model=OkEnvelope[dict[str, Any]])
async def remove_item(
    item_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Hard-delete a single Item node.

    Args:
        item_id: ID of the Item node to delete.

    Returns:
        Envelope confirming deletion.
    """
    await delete_item(session, item_id=item_id)
    return ok_response({"item_id": item_id})
