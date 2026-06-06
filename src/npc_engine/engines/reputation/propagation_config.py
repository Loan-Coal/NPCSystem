"""
Module: propagation_config
Layer: engines
Purpose: Pydantic model for reputation propagation tuning constants and YAML loader.
         Parses reputation_rules.yaml into a validated PropagationConfig instance.
Does NOT: perform graph queries, open sessions, or call any I/O beyond file reads.
Dependencies: pydantic, npc_engine.common.yaml_utils
Used by: npc_engine.engines.reputation.reputation_engine
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from npc_engine.common.yaml_utils import load_yaml_mapping


# ---------------------------------------------------------------------------
# Default config path (relative to this file)
# ---------------------------------------------------------------------------

_DEFAULT_YAML: Path = Path(__file__).parent / "reputation_rules.yaml"


class PropagationConfig(BaseModel):
    """Tunable constants for the 1-hop reputation propagation engine.

    Attributes:
        max_nudge_per_tick: Maximum absolute trust/affection delta applied per tick per pair.
        min_source_standing: Minimum Standing name the source NPC must have toward the player
            before their reputation is propagated. Compared as a Standing enum value.
        min_bridge_standing: Minimum Standing name required on the source→bridge edge
            before the bridge NPC is considered a valid intermediary.
        enabled: Feature flag. When False the engine exits immediately with no mutations.
    """

    max_nudge_per_tick: int = Field(ge=0, description="Max delta per NPC pair per tick.")
    min_source_standing: str = Field(description="Standing band name, e.g. FRIENDLY.")
    min_bridge_standing: str = Field(description="Standing band name, e.g. NEUTRAL.")
    enabled: bool = Field(description="Global on/off switch for this engine.")


def load_propagation_config(path: Path = _DEFAULT_YAML) -> PropagationConfig:
    """Load and validate propagation config from a YAML file.

    Args:
        path: Filesystem path to the YAML config file.
              Defaults to the bundled reputation_rules.yaml.

    Returns:
        Validated PropagationConfig instance.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        ValueError: If required fields are missing or have wrong types.
        pydantic.ValidationError: If Pydantic validation fails.
    """
    raw: dict[str, Any] = load_yaml_mapping(path, "reputation_rules.yaml must have a mapping root")
    return PropagationConfig(
        max_nudge_per_tick=int(raw["max_nudge_per_tick"]),
        min_source_standing=str(raw["min_source_standing"]),
        min_bridge_standing=str(raw["min_bridge_standing"]),
        enabled=bool(raw["enabled"]),
    )
