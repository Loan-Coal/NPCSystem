"""
Module: template_loader
Layer: engines
Purpose: Loads quest template YAML files from a directory at startup.
Does NOT: select templates or call LLMs.
Dependencies: common.yaml_utils, engines.quest_generation.slot_models
Dependencies injected: dir_path (via load_templates argument).
Used by: npc_engine.api.dependency_singletons (singleton construction)
"""

from __future__ import annotations

from typing import Any
from pathlib import Path

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.engines.quest_generation.slot_models import (
    QuestTemplateRecord,
    SlotDefinition,
)

_REQUIRED_FIELDS = ("id", "name", "archetype", "severity", "slot_definitions",
                    "description_template", "reward_template")


def load_templates(dir_path: Path) -> list[QuestTemplateRecord]:
    """Load all quest template YAML files from dir_path.

    Args:
        dir_path: Directory containing quest template YAML files.

    Returns:
        List of parsed QuestTemplateRecord instances (one per file).

    Raises:
        ValueError: If any template file is missing required fields or has
            duplicate IDs, or if no templates are found.
        FileNotFoundError: If dir_path does not exist.
    """
    yaml_files = sorted(dir_path.glob("*.yaml"))
    if not yaml_files:
        raise ValueError(f"no quest template YAML files found in {dir_path}")

    seen_ids: set[str] = set()
    records: list[QuestTemplateRecord] = []
    for yaml_path in yaml_files:
        raw = load_yaml_mapping(yaml_path, f"template file {yaml_path.name} must be a YAML mapping")
        _validate_required_fields(raw, yaml_path.name)
        template_id = str(raw["id"])
        if template_id in seen_ids:
            raise ValueError(f"duplicate quest template id: {template_id!r} in {yaml_path.name}")
        seen_ids.add(template_id)
        records.append(_parse_template(raw))
    return records


def _validate_required_fields(raw: dict[str, Any], filename: str) -> None:
    """Raise ValueError if any required field is absent."""
    for field in _REQUIRED_FIELDS:
        if field not in raw:
            raise ValueError(f"template {filename!r} missing required field '{field}'")


def _parse_template(raw: dict[str, Any]) -> QuestTemplateRecord:
    """Convert a raw YAML dict into a QuestTemplateRecord."""
    slot_defs_raw = raw["slot_definitions"]
    if not isinstance(slot_defs_raw, list):
        raise ValueError(
            f"template '{raw['id']}' slot_definitions must be a list"
        )
    slot_defs = tuple(
        SlotDefinition(
            name=str(entry["name"]),
            node_type=str(entry["node_type"]),
            required=bool(entry.get("required", True)),
        )
        for entry in slot_defs_raw
    )
    return QuestTemplateRecord(
        id=str(raw["id"]),
        name=str(raw["name"]),
        archetype=str(raw["archetype"]),
        severity=int(raw["severity"]),
        slot_definitions=slot_defs,
        description_template=str(raw["description_template"]),
        reward_template=str(raw["reward_template"]),
    )
