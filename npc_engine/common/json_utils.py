"""
json_utils.py - Shared JSON parse/serialize helpers with safe fallbacks.

Does NOT: enforce domain schema constraints.

Dependencies injected: None.
"""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(value: object) -> dict[str, Any]:
    """Return a JSON object from native dict or JSON string; otherwise {}."""

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
    """Return a JSON array from native list or JSON string; otherwise []."""

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
    """Serialize one value to JSON text with default encoder behavior."""

    return json.dumps(value)
