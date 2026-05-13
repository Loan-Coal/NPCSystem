"""
Module: trade_engine
Layer: engines
Purpose: Evaluates trade offers and executes atomic item+currency transfers on acceptance.
Does NOT: apply business-policy caps or call LLMs.
Dependencies injected: PricingEngine (via constructor), AsyncSession (at call site).
Dependencies: npc_engine.engines.economy.pricing_engine,
              npc_engine.graph.pricing_queries,
              npc_engine.graph.currency_writer,
              npc_engine.graph.item_writer
Used by: npc_engine.api.routes.economy
"""

from __future__ import annotations

import uuid

from neo4j import AsyncSession

from npc_engine.engines.economy.pricing_engine import PricingEngine
from npc_engine.engines.economy.trade_models import TradeResult
from npc_engine.graph.currency_writer import transfer_currency_atomic
from npc_engine.graph.item_writer import transfer_item_atomic
from npc_engine.graph.pricing_queries import (
    check_faction_membership,
    get_active_event_types_at_location,
    get_character_location_id,
    get_character_location_type,
)

_ACTIVE_EVENT_WINDOW_TICKS = 10


class TradeEngine:
    """Evaluates trade offers and executes transfers when a fair price is met.

    Accepts an offer if offered_price >= fair_price. On acceptance, the item
    is transferred atomically from seller to buyer, and currency from buyer to
    seller, in two separate graph transactions.
    """

    def __init__(self, pricing_engine: PricingEngine) -> None:
        """Initialise with a pre-constructed PricingEngine.

        Args:
            pricing_engine: Configured PricingEngine used for fair-price calculation.
        """
        self._pricing_engine = pricing_engine

    async def evaluate_offer(
        self,
        session: AsyncSession,
        buyer_id: str,
        seller_id: str,
        item_id: str,
        item_type: str,
        offered_price: int,
        current_tick: int = 0,
    ) -> TradeResult:
        """Evaluate a trade offer and execute transfers if accepted.

        Computes the fair price from the seller's location, active events there,
        and whether buyer and seller share a faction. Accepts if offered_price >=
        fair_price; rejects otherwise. On acceptance, transfers item seller→buyer
        and currency buyer→seller atomically.

        Args:
            session: Active Neo4j async session.
            buyer_id: ID of the character making the offer.
            seller_id: ID of the character selling the item.
            item_id: ID of the Item node being traded.
            item_type: Classification of the item for pricing (e.g. "sword").
            offered_price: Currency amount the buyer is offering.
            current_tick: Current game tick used to window active event lookups.

        Returns:
            TradeResult with accepted flag, fair_price, final_price, and rejection_reason.
        """
        location_type = await get_character_location_type(session, seller_id) or "unknown"
        location_id = await get_character_location_id(session, seller_id)

        active_event_types: list[str] = []
        if location_id is not None:
            since_tick = max(0, current_tick - _ACTIVE_EVENT_WINDOW_TICKS)
            active_event_types = await get_active_event_types_at_location(
                session, location_id, since_tick
            )

        is_faction_member = await check_faction_membership(session, buyer_id, seller_id)

        fair_price = self._pricing_engine.compute_price(
            item_type=item_type,
            location_type=location_type,
            active_event_types=active_event_types,
            is_faction_member=is_faction_member,
        )

        if offered_price < fair_price:
            return TradeResult(
                accepted=False,
                fair_price=fair_price,
                final_price=None,
                rejection_reason=f"Offered {offered_price} is below fair price {fair_price}.",
            )

        trade_key = str(uuid.uuid4())

        await transfer_item_atomic(
            session,
            source_id=seller_id,
            destination_id=buyer_id,
            item_id=item_id,
            quantity=1,
            reason="trade",
            request_id=trade_key,
            idempotency_key=f"item-{trade_key}",
            transfer_kind="trade",
        )

        await transfer_currency_atomic(
            session,
            source_id=buyer_id,
            destination_id=seller_id,
            amount=offered_price,
            reason="trade",
            request_id=trade_key,
            idempotency_key=f"currency-{trade_key}",
            session_scope=trade_key,
            transfer_kind="trade",
        )

        return TradeResult(
            accepted=True,
            fair_price=fair_price,
            final_price=offered_price,
            rejection_reason=None,
        )
