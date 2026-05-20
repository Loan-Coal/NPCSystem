"""
Module: pricing_rules_loader
Layer: engines
Purpose: Loads and validates economy pricing rules from a YAML file at startup.
Does NOT: execute graph queries or compute prices.
Dependencies: npc_engine.common.yaml_utils
Dependencies injected: path (via load_pricing_rules argument).
Used by: npc_engine.engines.economy.pricing_engine, npc_engine.api.dependency_singletons
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from npc_engine.common.yaml_utils import load_yaml_mapping


@dataclass(frozen=True)
class LocationModifier:
    """A price multiplier applied when item is sold at a specific location type.

    Attributes:
        location_type: The location classification this modifier applies to.
        item_type: Item classification this applies to; "any" matches all items.
        multiplier: Price multiplier (e.g. 1.5 = 50% more expensive).
    """

    location_type: str
    item_type: str
    multiplier: float


@dataclass(frozen=True)
class EventModifier:
    """A price multiplier applied when a specific event type is active at the location.

    Attributes:
        event_type: The event classification this modifier applies to.
        item_type: Item classification this applies to.
        multiplier: Price multiplier (e.g. 2.0 = double price).
    """

    event_type: str
    item_type: str
    multiplier: float


@dataclass(frozen=True)
class PricingRules:
    """Validated pricing rule set loaded from pricing_rules.yaml.

    Attributes:
        base_prices: Mapping of item_type → base integer price.
        default_price: Fallback price when item_type is not in base_prices.
        location_modifiers: Ordered list of location-based price multipliers.
        event_modifiers: Ordered list of event-based price multipliers.
        faction_discount: Fractional discount (0–1) for faction members.
    """

    base_prices: dict[str, int]
    default_price: int
    location_modifiers: tuple[LocationModifier, ...]
    event_modifiers: tuple[EventModifier, ...]
    faction_discount: float


def load_pricing_rules(path: Path) -> PricingRules:
    """Load and validate pricing rules from a YAML file.

    Args:
        path: Path to the pricing_rules.yaml file.

    Returns:
        Validated PricingRules instance.

    Raises:
        ValueError: If the YAML is malformed or a required field is missing.
        FileNotFoundError: If the file does not exist at path.
    """
    raw: dict[str, Any] = load_yaml_mapping(path, "pricing rules must have a mapping root")

    if "base_prices" not in raw:
        raise ValueError("pricing rules missing required field: 'base_prices'")
    if "faction_discount" not in raw:
        raise ValueError("pricing rules missing required field: 'faction_discount'")

    raw_base: dict[str, Any] = raw["base_prices"]
    default_price = int(raw_base.get("default", 5))
    base_prices: dict[str, int] = {k: int(v) for k, v in raw_base.items() if k != "default"}

    location_modifiers = tuple(
        LocationModifier(
            location_type=str(entry["location_type"]),
            item_type=str(entry["item_type"]),
            multiplier=float(entry["multiplier"]),
        )
        for entry in raw.get("location_modifiers", [])
    )

    event_modifiers = tuple(
        EventModifier(
            event_type=str(entry["event_type"]),
            item_type=str(entry["item_type"]),
            multiplier=float(entry["multiplier"]),
        )
        for entry in raw.get("event_modifiers", [])
    )

    return PricingRules(
        base_prices=base_prices,
        default_price=default_price,
        location_modifiers=location_modifiers,
        event_modifiers=event_modifiers,
        faction_discount=float(raw["faction_discount"]),
    )
