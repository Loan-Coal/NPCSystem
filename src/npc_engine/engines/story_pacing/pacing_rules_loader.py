"""
Module: pacing_rules_loader
Layer: engines
Purpose: Loads and validates story pacing rules from a YAML file at startup.
Does NOT: execute graph queries or apply world state changes.
Dependencies: npc_engine.common.yaml_utils
Dependencies injected: path (via load_pacing_rules argument).
Used by: npc_engine.engines.story_pacing.story_pacing_engine
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from npc_engine.common.yaml_utils import load_yaml_mapping


@dataclass(frozen=True)
class PacingRules:
    """Validated story pacing rule set loaded from YAML.

    Attributes:
        high_severity_quest_threshold: Quest severity >= this triggers suppression.
        suppression_event_severity_cap: max_event_severity written when suppressed.
        suppression_quest_rate: quest_generation_rate multiplier when suppressed.
        cooldown_ticks: Ticks since last major event before pacing relaxes.
        major_event_severity_floor: Events above this count as major.
    """

    high_severity_quest_threshold: int
    suppression_event_severity_cap: int
    suppression_quest_rate: float
    cooldown_ticks: int
    major_event_severity_floor: int


def load_pacing_rules(path: Path) -> PacingRules:
    """Load and validate story pacing rules from a YAML file.

    Args:
        path: Path to the pacing_rules.yaml file.

    Returns:
        Validated PacingRules instance.

    Raises:
        ValueError: If the YAML is malformed or a required field is missing.
        FileNotFoundError: If the file does not exist at path.
    """
    raw: dict[str, Any] = load_yaml_mapping(path, "story pacing rules must have a mapping root")

    required_int_fields = (
        "high_severity_quest_threshold",
        "suppression_event_severity_cap",
        "cooldown_ticks",
        "major_event_severity_floor",
    )
    for field in required_int_fields:
        if field not in raw:
            raise ValueError(f"story pacing rules missing required field: {field!r}")

    if "suppression_quest_rate" not in raw:
        raise ValueError("story pacing rules missing required field: 'suppression_quest_rate'")

    return PacingRules(
        high_severity_quest_threshold=int(raw["high_severity_quest_threshold"]),
        suppression_event_severity_cap=int(raw["suppression_event_severity_cap"]),
        suppression_quest_rate=float(raw["suppression_quest_rate"]),
        cooldown_ticks=int(raw["cooldown_ticks"]),
        major_event_severity_floor=int(raw["major_event_severity_floor"]),
    )
