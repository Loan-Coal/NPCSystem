"""
Module: gossip_config
Layer: engines/gossip
Purpose: Faction weight config dataclass and YAML loader for the gossip engine.
Does NOT: perform any I/O beyond reading the packaged config.yaml once at load time.
Dependencies injected: None.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"


@dataclass(frozen=True)
class GossipWeightConfig:
    """Immutable faction-weight multipliers for gossip pair selection and distortion.

    Confidence band thresholds (EXP-213) are also stored here so that no magic
    numbers appear in Python code.  See config.yaml for tuning guidance.
    """

    same_faction_boost: float = 2.0
    allied_boost: float = 1.5
    hostile_penalty: float = 0.1
    hostile_distortion_factor: float = 1.5
    # Confidence bands for distortion-type biasing (EXP-213).
    confidence_high_threshold: int = 70
    confidence_low_threshold: int = 30


def load_gossip_config(path: Path = _DEFAULT_CONFIG_PATH) -> GossipWeightConfig:
    """Load GossipWeightConfig from a YAML file, falling back to defaults for missing keys.

    Args:
        path: Path to the YAML config file. Defaults to the packaged config.yaml.

    Returns:
        GossipWeightConfig populated from the file, using dataclass defaults for absent keys.
    """
    if not path.exists():
        return GossipWeightConfig()
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return GossipWeightConfig(
        same_faction_boost=float(raw.get("same_faction_boost", GossipWeightConfig.same_faction_boost)),
        allied_boost=float(raw.get("allied_boost", GossipWeightConfig.allied_boost)),
        hostile_penalty=float(raw.get("hostile_penalty", GossipWeightConfig.hostile_penalty)),
        hostile_distortion_factor=float(
            raw.get("hostile_distortion_factor", GossipWeightConfig.hostile_distortion_factor)
        ),
        confidence_high_threshold=int(
            raw.get("confidence_high_threshold", GossipWeightConfig.confidence_high_threshold)
        ),
        confidence_low_threshold=int(
            raw.get("confidence_low_threshold", GossipWeightConfig.confidence_low_threshold)
        ),
    )
