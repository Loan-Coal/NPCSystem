"""
Unit tests for the economy engine (Phase 4.4).

Tests use fake async session stubs — no live DB required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.asyncio
async def test_trade_engine_accepts_fair_offer() -> None:
    """offered_price >= fair_price → accepted=True, transfers executed."""
    rules = _make_rules(base_prices={"sword": 50})
    pricing_engine = PricingEngine(rules=rules)
    trade_engine = TradeEngine(pricing_engine=pricing_engine)

    mock_session = MagicMock()

    with (
        patch("npc_engine.engines.economy.trade_engine.get_character_location_type", new=AsyncMock(return_value="village")),
        patch("npc_engine.engines.economy.trade_engine.get_character_location_id", new=AsyncMock(return_value=None)),
        patch("npc_engine.engines.economy.trade_engine.check_faction_membership", new=AsyncMock(return_value=False)),
        patch("npc_engine.engines.economy.trade_engine.transfer_item_atomic", new=AsyncMock()) as mock_item,
        patch("npc_engine.engines.economy.trade_engine.transfer_currency_atomic", new=AsyncMock()) as mock_currency,
    ):
        result: TradeResult = await trade_engine.evaluate_offer(
            session=mock_session,
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
    mock_item.assert_called_once()
    mock_currency.assert_called_once()


@pytest.mark.asyncio
async def test_trade_engine_rejects_low_offer() -> None:
    """offered_price < fair_price → accepted=False, no transfers executed."""
    rules = _make_rules(base_prices={"sword": 50})
    pricing_engine = PricingEngine(rules=rules)
    trade_engine = TradeEngine(pricing_engine=pricing_engine)

    mock_session = MagicMock()

    with (
        patch("npc_engine.engines.economy.trade_engine.get_character_location_type", new=AsyncMock(return_value="village")),
        patch("npc_engine.engines.economy.trade_engine.get_character_location_id", new=AsyncMock(return_value=None)),
        patch("npc_engine.engines.economy.trade_engine.check_faction_membership", new=AsyncMock(return_value=False)),
        patch("npc_engine.engines.economy.trade_engine.transfer_item_atomic", new=AsyncMock()) as mock_item,
        patch("npc_engine.engines.economy.trade_engine.transfer_currency_atomic", new=AsyncMock()) as mock_currency,
    ):
        result: TradeResult = await trade_engine.evaluate_offer(
            session=mock_session,
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
    mock_item.assert_not_called()
    mock_currency.assert_not_called()
