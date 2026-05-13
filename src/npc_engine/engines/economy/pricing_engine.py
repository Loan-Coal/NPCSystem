"""
Module: pricing_engine
Layer: engines
Purpose: Pure deterministic price computation for items given location, events, and faction status.
Does NOT: perform I/O, query the graph, or persist any state.
Dependencies: npc_engine.engines.economy.pricing_rules_loader
Dependencies injected: PricingRules (via constructor).
Used by: npc_engine.engines.economy.trade_engine, npc_engine.api.routes.economy
"""

from __future__ import annotations

import math

from npc_engine.engines.economy.pricing_rules_loader import PricingRules


class PricingEngine:
    """Computes item prices using a rule set loaded from pricing_rules.yaml.

    Modifiers are applied multiplicatively in order: location, then event,
    then faction discount. The result is floored to an integer.
    """

    def __init__(self, rules: PricingRules) -> None:
        """Initialise with a validated pricing rule set.

        Args:
            rules: Loaded and validated PricingRules instance.
        """
        self._rules = rules

    def compute_price(
        self,
        item_type: str,
        location_type: str,
        active_event_types: list[str],
        is_faction_member: bool,
    ) -> int:
        """Compute the final item price at a location with optional event and faction modifiers.

        All modifiers stack multiplicatively. Faction discount is applied last.
        The result is floored to a non-negative integer.

        Args:
            item_type: Classification of the item (e.g. "sword", "potion").
            location_type: Classification of the current location (e.g. "frontier", "market").
            active_event_types: Event types currently active at the location.
            is_faction_member: True if buyer shares a faction with the seller.

        Returns:
            Final item price as a non-negative integer (floor).
        """
        base = float(self._rules.base_prices.get(item_type, self._rules.default_price))
        price = base

        for mod in self._rules.location_modifiers:
            if mod.location_type == location_type and (mod.item_type == "any" or mod.item_type == item_type):
                price *= mod.multiplier

        for event_type in active_event_types:
            for mod in self._rules.event_modifiers:
                if mod.event_type == event_type and mod.item_type == item_type:
                    price *= mod.multiplier

        if is_faction_member:
            price *= 1.0 - self._rules.faction_discount

        return max(0, math.floor(price))
