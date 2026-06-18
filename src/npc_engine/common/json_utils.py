"""
json_utils.py - Shared JSON parse/serialize helpers with safe fallbacks.
Layer: config
Purpose: (auto-detected — review)

Does NOT: enforce domain schema constraints.

Dependencies injected: None.
"""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(value: object) -> dict[str, Any]:
    """Return a JSON object from native dict or JSON string; otherwise {}.

    Args:
        value: object — raw value from an external source (dict, JSON string, or other).

    Returns:
        Parsed dict if value is a dict or a JSON string encoding a dict; empty dict otherwise.
    """

    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def parse_json_list(value: object) -> list[Any]:
    """Return a JSON array from native list or JSON string; otherwise [].

    Args:
        value: object — raw value from an external source (list, JSON string, or other).

    Returns:
        Parsed list if value is a list or a JSON string encoding a list; empty list otherwise.
    """

    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return []
        if isinstance(parsed, list):
            return parsed
    return []


def dump_json(value: object) -> str:
    """Serialize one value to JSON text with default encoder behavior.

    Args:
        value: object — any JSON-serializable Python value.

    Returns:
        JSON string representation of value.
    """

    return json.dumps(value)
