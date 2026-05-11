"""
Module: disruption_loader
Layer: engines/events
Purpose: Dataclass and YAML loader for routine-disruption rules triggered by events.
Does NOT: execute any disruption logic or write to the graph.
Dependencies injected: None.
Used by: npc_engine.engines.events.event_handler
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from npc_engine.common.yaml_utils import load_yaml_mapping

_DEFAULT_RULES_PATH = Path(__file__).parent / "disruption_rules.yaml"


@dataclass(frozen=True)
class DisruptionRule:
    """Immutable rule that maps an event condition to a routine override."""

    override_location: str
    duration_ticks: int
    trigger_event_types: tuple[str, ...] = field(default_factory=tuple)
    trigger_severity_min: int | None = None


def load_disruption_rules(path: Path = _DEFAULT_RULES_PATH) -> list[DisruptionRule]:
    """Load disruption rules from a YAML file.

    Args:
        path: Path to the YAML rules file.  Defaults to the packaged disruption_rules.yaml.

    Returns:
        List of DisruptionRule objects.  Returns an empty list when the file does not exist.

    Raises:
        ValueError: if the YAML root is not a mapping or 'rules' value is not a list.
    """
    if not path.exists():
        return []
    mapping = load_yaml_mapping(path, f"disruption rules file must be a YAML mapping: {path}")
    raw_rules = mapping.get("rules", [])
    if not isinstance(raw_rules, list):
        raise ValueError(f"'rules' must be a list in {path}")
    result: list[DisruptionRule] = []
    for raw in raw_rules:
        event_types = tuple(raw.get("trigger_event_types", []))
        severity_min: int | None = raw.get("trigger_severity_min")
        result.append(
            DisruptionRule(
                override_location=str(raw["override_location"]),
                duration_ticks=int(raw["duration_ticks"]),
                trigger_event_types=event_types,
                trigger_severity_min=int(severity_min) if severity_min is not None else None,
            )
        )
    return result
