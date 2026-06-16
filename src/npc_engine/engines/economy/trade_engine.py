"""
Module: trade_engine
Layer: engines
Purpose: Evaluates trade offers and executes atomic item+currency transfers on acceptance.
Does NOT: apply business-policy caps, run Cypher, hold a session, or call LLMs.
Dependencies injected: PricingEngine + EconomyGraphPort (via constructor).
Dependencies: npc_engine.engines.economy.pricing_engine,
              npc_engine.engines.ports.economy_port (EconomyGraphPort)
Used by: npc_engine.api.routes.economy
"""

from __future__ import annotations

import uuid

from npc_engine.engines.economy.pricing_engine import PricingEngine
from npc_engine.engines.economy.trade_models import TradeResult
from npc_engine.engines.ports.economy_port import EconomyGraphPort

_ACTIVE_EVENT_WINDOW_TICKS = 10


class TradeEngine:
    """Evaluates trade offers and executes transfers when a fair price is met.

    Accepts an offer if offered_price >= fair_price. On acceptance, the item
    is transferred atomically from seller to buyer, and currency from buyer to
    seller, in two separate graph transactions.
    """

    def __init__(self, pricing_engine: PricingEngine, economy_repo: EconomyGraphPort) -> None:
        """Initialise with a pre-constructed PricingEngine and economy graph port.

        Args:
            pricing_engine: Configured PricingEngine used for fair-price calculation.
            economy_repo: EconomyGraphPort for pricing-context reads + atomic transfers.
        """
        self._pricing_engine = pricing_engine
        self._economy = economy_repo

    async def evaluate_offer(
        self,
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
            buyer_id: ID of the character making the offer.
            seller_id: ID of the character selling the item.
            item_id: ID of the Item node being traded.
            item_type: Classification of the item for pricing (e.g. "sword").
            offered_price: Currency amount the buyer is offering.
            current_tick: Current game tick used to window active event lookups.

        Returns:
            TradeResult with accepted flag, fair_price, final_price, and rejection_reason.
        """
        fair_price = await self._compute_fair_price(seller_id, buyer_id, item_type, current_tick)

        if offered_price < fair_price:
            return TradeResult(
                accepted=False,
                fair_price=fair_price,
                final_price=None,
                rejection_reason=f"Offered {offered_price} is below fair price {fair_price}.",
            )

        await self._execute_transfers(buyer_id, seller_id, item_id, offered_price)
        return TradeResult(
            accepted=True,
            fair_price=fair_price,
            final_price=offered_price,
            rejection_reason=None,
        )

    async def _compute_fair_price(
        self, seller_id: str, buyer_id: str, item_type: str, current_tick: int
    ) -> int:
        """Read the seller's pricing context via the port and compute the fair price."""
        location_type = await self._economy.get_character_location_type(character_id=seller_id) or "unknown"
        location_id = await self._economy.get_character_location_id(character_id=seller_id)

        active_event_types: list[str] = []
        if location_id is not None:
            since_tick = max(0, current_tick - _ACTIVE_EVENT_WINDOW_TICKS)
            active_event_types = await self._economy.get_active_event_types_at_location(
                location_id=location_id, since_tick=since_tick
            )

        is_faction_member = await self._economy.check_faction_membership(
            buyer_id=buyer_id, seller_id=seller_id
        )
        return self._pricing_engine.compute_price(
            item_type=item_type,
            location_type=location_type,
            active_event_types=active_event_types,
            is_faction_member=is_faction_member,
        )

    async def _execute_transfers(
        self, buyer_id: str, seller_id: str, item_id: str, offered_price: int
    ) -> None:
        """Atomically transfer the item seller→buyer and currency buyer→seller."""
        trade_key = str(uuid.uuid4())
        await self._economy.transfer_item_atomic(
            source_id=seller_id,
            destination_id=buyer_id,
            item_id=item_id,
            quantity=1,
            reason="trade",
            request_id=trade_key,
            idempotency_key=f"item-{trade_key}",
            transfer_kind="trade",
        )
        await self._economy.transfer_currency_atomic(
            source_id=buyer_id,
            destination_id=seller_id,
            amount=offered_price,
            reason="trade",
            request_id=trade_key,
            idempotency_key=f"currency-{trade_key}",
            session_scope=trade_key,
            transfer_kind="trade",
        )
