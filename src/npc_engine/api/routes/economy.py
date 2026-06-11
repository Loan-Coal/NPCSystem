"""
Module: economy
Layer: api
Purpose: Admin HTTP routes for item pricing queries and trade offer evaluation.
Does NOT: perform authentication or implement business-policy caps.
Dependencies: engines.economy.pricing_engine, engines.economy.trade_engine,
              graph.pricing_queries, api.dependencies.get_db_session
Dependencies injected: AsyncSession, PricingEngine, TradeEngine (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

import logging

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.dependency_singletons import get_pricing_engine, get_trade_engine
from npc_engine.api.route_helpers import OkEnvelope, ok_response
from npc_engine.engines.economy.pricing_engine import PricingEngine
from npc_engine.engines.economy.trade_engine import TradeEngine
from npc_engine.graph.pricing_queries import (
    get_active_event_types_at_location,
    get_character_location_id,
    get_character_location_type,
)
from npc_engine.utils.errors import (
    CurrencyInsufficientFundsError,
    ItemTransferValidationError,
    NodeNotFoundError,
)

router = APIRouter(prefix="/economy", tags=["economy"])
_logger = logging.getLogger(__name__)


class TradeOfferRequest(BaseModel):
    """Request body for POST /economy/trade."""

    buyer_id: str = Field(..., min_length=1)
    seller_id: str = Field(..., min_length=1)
    item_id: str = Field(..., min_length=1)
    item_type: str = Field(..., min_length=1)
    offered_price: int = Field(..., ge=0)
    current_tick: int = Field(default=0, ge=0)

    model_config = ConfigDict(frozen=True)


@router.get("/price", response_model=OkEnvelope[dict[str, Any]])
async def get_item_price(
    item_type: str = Query(..., min_length=1),
    character_id: str = Query(..., min_length=1),
    session: AsyncSession = Depends(get_db_session),
    pricing_engine: PricingEngine = Depends(get_pricing_engine),
) -> dict[str, Any]:
    """Compute the current fair price for an item at a character's location.

    Args:
        item_type: Classification of the item (e.g. "sword", "potion").
        character_id: ID of the character at whose location the price is computed.
        session: Active Neo4j async session.
        pricing_engine: Singleton pricing engine.

    Returns:
        Envelope with the computed integer price.
    """
    location_type = await get_character_location_type(session, character_id) or "unknown"
    location_id = await get_character_location_id(session, character_id)

    active_event_types: list[str] = []
    if location_id is not None:
        active_event_types = await get_active_event_types_at_location(
            session, location_id, since_tick=0
        )

    price = pricing_engine.compute_price(
        item_type=item_type,
        location_type=location_type,
        active_event_types=active_event_types,
        is_faction_member=False,
    )
    return ok_response({"price": price})


@router.post("/trade", response_model=OkEnvelope[dict[str, Any]])
async def evaluate_trade(
    body: TradeOfferRequest,
    session: AsyncSession = Depends(get_db_session),
    trade_engine: TradeEngine = Depends(get_trade_engine),
) -> dict[str, Any]:
    """Evaluate a trade offer and execute transfers if accepted.

    Args:
        body: Buyer/seller/item/price details.
        session: Active Neo4j async session.
        trade_engine: Singleton trade engine.

    Returns:
        Envelope with TradeResult fields: accepted, fair_price, final_price, rejection_reason.
    """
    _logger.info(
        "trade_request: buyer=%s seller=%s item=%s item_type=%s price=%d",
        body.buyer_id, body.seller_id, body.item_id, body.item_type, body.offered_price,
    )
    try:
        result = await trade_engine.evaluate_offer(
            session=session,
            buyer_id=body.buyer_id,
            seller_id=body.seller_id,
            item_id=body.item_id,
            item_type=body.item_type,
            offered_price=body.offered_price,
            current_tick=body.current_tick,
        )
    except CurrencyInsufficientFundsError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INSUFFICIENT_FUNDS", "message": "The buyer does not have enough gold."},
        ) from exc
    except NodeNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "CHARACTER_NOT_FOUND", "message": f"Character not found: {exc.node_id}"},
        ) from exc
    except ItemTransferValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": "The seller does not own this item."},
        ) from exc
    return ok_response({
        "accepted": result.accepted,
        "fair_price": result.fair_price,
        "final_price": result.final_price,
        "rejection_reason": result.rejection_reason,
    })
