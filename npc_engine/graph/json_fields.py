"""
json_fields.py - Shared JSON field serialization helpers for graph write payloads.

Does NOT: execute graph queries.

Dependencies injected: None.
"""

from __future__ import annotations

import json
from typing import Any


def serialize_provenance_field(payload: dict[str, Any]) -> dict[str, Any]:
    """Return payload with provenance dict serialized to deterministic JSON text."""

    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return payload
    return {
        **payload,
        "provenance": json.dumps(provenance, sort_keys=True),
    }
