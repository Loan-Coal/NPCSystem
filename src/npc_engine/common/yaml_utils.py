"""
yaml_utils.py - Shared YAML loading helpers for mapping-root config files.
Layer: config
Purpose: (auto-detected — review)

Does NOT: validate domain-specific schema contracts.

Dependencies injected: None.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml_mapping(path: Path, root_error_message: str) -> dict[str, Any]:
    """Read YAML from disk and require a mapping root object.

    Args:
        path: Path — filesystem path to the YAML file.
        root_error_message: str — error text raised when the YAML root is not a mapping.

    Returns:
        Parsed dict representing the YAML mapping.

    Raises:
        ValueError: if the YAML root is not a dict (e.g., a list or scalar).
        FileNotFoundError: propagated from Path.read_text if the file does not exist.
    """

    raw_content = path.read_text(encoding="utf-8")
    loaded: Any = yaml.safe_load(raw_content)
    if not isinstance(loaded, dict):
        raise ValueError(root_error_message)
    return loaded
