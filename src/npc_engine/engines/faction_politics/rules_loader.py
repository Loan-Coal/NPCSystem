"""
Module: rules_loader
Layer: engines
Purpose: Loads and validates faction politics rules from a YAML file at startup.
Does NOT: execute graph queries or apply standing changes.
Dependencies injected: path (via load_rules argument).
Used by: npc_engine.engines.faction_politics.faction_politics_engine
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from npc_engine.common.yaml_utils import load_yaml_mapping


@dataclass(frozen=True)
class FactionPoliticsRule:
    """One rule that maps an event type to a standing delta."""

    id: str
    event_type: str
    standing_delta: int


@dataclass(frozen=True)
class DecayConfig:
    """Configuration for how standings drift toward neutral over time."""

    rate_per_tick: int
    min_magnitude: int


@dataclass(frozen=True)
class FactionPoliticsRules:
    """Complete faction politics rule set loaded from YAML."""

    decay: DecayConfig
    rules: tuple[FactionPoliticsRule, ...]


def load_rules(path: Path) -> FactionPoliticsRules:
    """Load and validate faction politics rules from a YAML file.

    Args:
        path: Path to the rules YAML file.

    Returns:
        Validated FactionPoliticsRules instance.

    Raises:
        ValueError: If the YAML is malformed, a required field is missing,
            or rule IDs are not unique.
        FileNotFoundError: If the file does not exist at path.
    """
    raw: dict[str, Any] = load_yaml_mapping(path, "faction politics rules must have a mapping root")

    decay_raw = raw.get("decay")
    if not isinstance(decay_raw, dict):
        raise ValueError("faction politics rules missing required 'decay' block")
    decay = DecayConfig(
        rate_per_tick=int(decay_raw["rate_per_tick"]),
        min_magnitude=int(decay_raw["min_magnitude"]),
    )

    rules_raw = raw.get("rules", [])
    if not isinstance(rules_raw, list):
        raise ValueError("faction politics rules 'rules' must be a list")

    seen_ids: set[str] = set()
    parsed: list[FactionPoliticsRule] = []
    for entry in rules_raw:
        rule_id = str(entry["id"])
        if rule_id in seen_ids:
            raise ValueError(f"duplicate faction politics rule id: {rule_id!r}")
        seen_ids.add(rule_id)
        parsed.append(FactionPoliticsRule(
            id=rule_id,
            event_type=str(entry["event_type"]),
            standing_delta=int(entry["standing_delta"]),
        ))

    return FactionPoliticsRules(decay=decay, rules=tuple(parsed))
