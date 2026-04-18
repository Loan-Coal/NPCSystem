"""
yaml_utils.py - Shared YAML loading helpers for mapping-root config files.

Does NOT: validate domain-specific schema contracts.

Dependencies injected: None.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml_mapping(path: Path, root_error_message: str) -> dict[str, Any]:
    """Read YAML from disk and require a mapping root object."""

    raw_content = path.read_text(encoding="utf-8")
    loaded: Any = yaml.safe_load(raw_content)
    if not isinstance(loaded, dict):
        raise ValueError(root_error_message)
    return loaded
