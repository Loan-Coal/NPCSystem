"""
Module: prefix_loader
Layer: engines
Purpose: Load and cache distortion prefix strings from the YAML config file.
Dependencies: pathlib (stdlib), yaml (pyyaml)
Used by: engines/gossip/strategies/exaggeration.py,
         engines/gossip/strategies/role_swap.py,
         engines/gossip/strategies/timeline_shift.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml

# ---------------------------------------------------------------------------
# YAML path: resolved relative to this file so the loader works regardless of
# the working directory or how the package is installed.
# Resolves to: src/npc_engine/prompts/gossip/distortion.yaml
# ---------------------------------------------------------------------------
_YAML_PATH: Final[Path] = (
    Path(__file__).parent  # strategies/
    / ".."  # gossip/
    / ".."  # engines/
    / ".."  # npc_engine/
    / "prompts"
    / "gossip"
    / "distortion.yaml"
).resolve()

# Module-level cache: loaded once on first call, reused thereafter.
_PREFIX_CACHE: dict[str, str] | None = None


def _load_prefixes() -> dict[str, str]:
    """Read and parse the distortion YAML file into a plain dict.

    Returns:
        Mapping from strategy key to prefix string.

    Raises:
        FileNotFoundError: When distortion.yaml cannot be found at the expected path.
        yaml.YAMLError: When the YAML is malformed.
    """
    with _YAML_PATH.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return {k: str(v) for k, v in raw.items() if not k.startswith("#")}


def get_distortion_prefix(strategy_key: str) -> str:
    """Return the distortion prefix string for the given strategy key.

    The YAML file is read once and the result cached in ``_PREFIX_CACHE``.
    Subsequent calls return from cache without any I/O.

    Args:
        strategy_key: One of ``"exaggeration"``, ``"role_swap"``,
            ``"timeline_shift"`` (keys defined in distortion.yaml).

    Returns:
        The prefix string for the requested strategy.

    Raises:
        KeyError: When *strategy_key* is not present in the YAML file.
        FileNotFoundError: When distortion.yaml cannot be located.
    """
    global _PREFIX_CACHE  # noqa: PLW0603 — intentional module-level cache
    if _PREFIX_CACHE is None:
        _PREFIX_CACHE = _load_prefixes()
    if strategy_key not in _PREFIX_CACHE:
        raise KeyError(
            f"No distortion prefix found for strategy key {strategy_key!r}. "
            f"Available keys: {sorted(_PREFIX_CACHE)}"
        )
    return _PREFIX_CACHE[strategy_key]
