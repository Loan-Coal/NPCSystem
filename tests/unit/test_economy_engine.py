"""
Unit tests for the economy engine (Phase 4.4).

Tests use fake async session stubs — no live DB required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.economy.pricing_engine import PricingEngine
from npc_engine.engines.economy.pricing_rules_loader import PricingRules, load_pricing_rules
from npc_engine.engines.economy.trade_engine import TradeEngine
from npc_engine.engines.economy.trade_models import TradeResult


_RULES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "npc_engine" / "engines" / "economy" / "pricing_rules.yaml"
)


def _make_rules(
    base_prices: dict | None = None,
    location_modifiers: tuple = (),
    event_modifiers: tuple = (),
    faction_discount: float = 0.1,
    default_price: int = 5,
) -> PricingRules:
    """Build a PricingRules instance with sensible defaults for testing."""
    return PricingRules(
        base_prices=base_prices or {"sword": 50, "potion": 20},
        default_price=default_price,
        location_modifiers=location_modifiers,
        event_modifiers=event_modifiers,
        faction_discount=faction_discount,
    )


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------


def test_pricing_rules_loader_loads_yaml() -> None:
    """load_pricing_rules reads the real pricing_rules.yaml and returns correct fields."""
    rules = load_pricing_rules(_RULES_PATH)

    assert "sword" in rules.base_prices
    assert rules.base_prices["sword"] == 50
    assert rules.default_price == 5
    assert len(rules.location_modifiers) > 0
    assert len(rules.event_modifiers) > 0
    assert rules.faction_discount == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# PricingEngine pure computation tests
# ---------------------------------------------------------------------------


def test_compute_price_base_only() -> None:
    """No location or event modifiers → base price returned unchanged."""
    rules = _make_rules(base_prices={"sword": 50})
    engine = PricingEngine(rules=rules)

    price = engine.compute_price(
        item_type="sword",
        location_type="village",
        active_event_types=[],
        is_faction_member=False,
    )

    assert price == 50


def test_compute_price_location_modifier() -> None:
    """frontier + sword modifier (1.5x) raises sword from 50 to 75."""
    from npc_engine.engines.economy.pricing_rules_loader import LocationModifier

    rules = _make_rules(
        base_prices={"sword": 50},
        location_modifiers=(LocationModifier(location_type="frontier", item_type="sword", multiplier=1.5),),
    )
    engine = PricingEngine(rules=rules)

    price = engine.compute_price(
        item_type="sword",
        location_type="frontier",
        active_event_types=[],
        is_faction_member=False,
    )

    assert price == 75


def test_compute_price_event_modifier() -> None:
    """war event → weapon modifier (2.0x) doubles the base price."""
    from npc_engine.engines.economy.pricing_rules_loader import EventModifier

    rules = _make_rules(
        base_prices={"sword": 50},
        event_modifiers=(EventModifier(event_type="war", item_type="sword", multiplier=2.0),),
    )
    engine = PricingEngine(rules=rules)

    price = engine.compute_price(
        item_type="sword",
        location_type="village",
        active_event_types=["war"],
        is_faction_member=False,
    )

    assert price == 100


def test_compute_price_faction_discount() -> None:
    """Faction member receives 10% off the base price (50 → 45)."""
    rules = _make_rules(base_prices={"sword": 50}, faction_discount=0.1)
    engine = PricingEngine(rules=rules)

    price = engine.compute_price(
        item_type="sword",
        location_type="village",
        active_event_types=[],
        is_faction_member=True,
    )

    assert price == 45


def test_compute_price_stacked_modifiers() -> None:
    """Location modifier (1.5x) and event modifier (2.0x) stack multiplicatively: 50*1.5*2 = 150."""
    from npc_engine.engines.economy.pricing_rules_loader import EventModifier, LocationModifier

    rules = _make_rules(
        base_prices={"sword": 50},
        location_modifiers=(LocationModifier(location_type="frontier", item_type="sword", multiplier=1.5),),
        event_modifiers=(EventModifier(event_type="war", item_type="sword", multiplier=2.0),),
    )
    engine = PricingEngine(rules=rules)

    price = engine.compute_price(
        item_type="sword",
        location_type="frontier",
        active_event_types=["war"],
        is_faction_member=False,
    )

    assert price == 150


# ---------------------------------------------------------------------------
# TradeEngine tests (async, with mocked graph calls)
# ---------------------------------------------------------------------------


def _economy_port(location_type: str = "village", location_id: str | None = None,
                  faction: bool = False) -> AsyncMock:
    """EconomyGraphPort double with configurable read returns."""
    port = AsyncMock()
    port.get_character_location_type.return_value = location_type
    port.get_character_location_id.return_value = location_id
    port.get_active_event_types_at_location.return_value = []
    port.check_faction_membership.return_value = faction
    return port


@pytest.mark.asyncio
async def test_trade_engine_accepts_fair_offer() -> None:
    """offered_price >= fair_price → accepted=True, transfers executed via the port."""
    pricing_engine = PricingEngine(rules=_make_rules(base_prices={"sword": 50}))
    port = _economy_port()
    trade_engine = TradeEngine(pricing_engine=pricing_engine, economy_repo=port)

    result: TradeResult = await trade_engine.evaluate_offer(
        buyer_id="buyer-1",
        seller_id="seller-1",
        item_id="item-sword-1",
        item_type="sword",
        offered_price=50,
    )

    assert result.accepted is True
    assert result.fair_price == 50
    assert result.final_price == 50
    assert result.rejection_reason is None
    port.transfer_item_atomic.assert_awaited_once()
    port.transfer_currency_atomic.assert_awaited_once()


@pytest.mark.asyncio
async def test_trade_engine_rejects_low_offer() -> None:
    """offered_price < fair_price → accepted=False, no transfers executed."""
    pricing_engine = PricingEngine(rules=_make_rules(base_prices={"sword": 50}))
    port = _economy_port()
    trade_engine = TradeEngine(pricing_engine=pricing_engine, economy_repo=port)

    result: TradeResult = await trade_engine.evaluate_offer(
        buyer_id="buyer-1",
        seller_id="seller-1",
        item_id="item-sword-1",
        item_type="sword",
        offered_price=30,
    )

    assert result.accepted is False
    assert result.fair_price == 50
    assert result.final_price is None
    assert result.rejection_reason is not None
    port.transfer_item_atomic.assert_not_awaited()
    port.transfer_currency_atomic.assert_not_awaited()
