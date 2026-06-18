"""
context_utils.py - Shared retrieval helpers for token estimation and key parsing.
Layer: retrieval
Purpose: (auto-detected — review)

Does NOT: enforce tier budgets or fetch graph/vector data.

Dependencies injected: None.
"""

from __future__ import annotations

import json
from typing import Any


CHARS_PER_TOKEN_ESTIMATE = 4

_LOW_VALUE_FIELDS: frozenset[str] = frozenset({
    "actor_id", "location_id", "schema_version", "id",
    "created_at_game_time",
})


def estimate_tokens(text: str) -> int:
    """Approximate token count using 4 characters per token heuristic.

    Args:
        text: Text to count tokens for.

    Returns:
        Estimated token count; always at least 1.
    """

    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def parse_node_identity(key: str) -> tuple[str, str]:
    """Parse ``type:id`` or ``type:id:suffix`` identifiers into (type, id) parts.

    Args:
        key: Colon-separated node identity string (1 to 3+ segments).

    Returns:
        Tuple of (node_type, node_id). Single-segment keys return (key, key).
    """

    parts = key.split(":")
    if len(parts) == 1:
        return key, key
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], ":".join(parts[1:])


def serialize_json(
    value: Any,
    *,
    compact: bool = False,
    strip_nulls: bool = False,
    strip_fields: frozenset[str] | None = None,
) -> str:
    """Serialize a value to JSON with deterministic key ordering.

    Args:
        value: JSON-serializable value to serialize.
        compact: When True, omits spaces around separators to minimize size.
        strip_nulls: When True, removes keys whose values are None.
        strip_fields: Optional set of field names to remove regardless of value.

    Returns:
        JSON string with ASCII encoding and sorted keys.
    """

    if strip_nulls or strip_fields:
        value = _clean(value, strip_nulls=strip_nulls, strip_fields=strip_fields or frozenset())
    separators = (",", ":") if compact else None
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=separators, default=_json_default
    )


def _json_default(obj: Any) -> str:
    """Fallback encoder for values json.dumps cannot natively serialize.

    Converts temporal types (Python datetime/date/time and Neo4j DateTime/Date/Time,
    which all expose isoformat) to ISO strings; any other non-native object degrades
    to its str() form. Keeps serialize_json robust against raw graph values (e.g.
    second-hop event rows) without requiring every caller to pre-normalize.

    Args:
        obj: A value json.dumps could not encode with the default JSON types.
    Returns:
        A JSON-safe string representation of obj.
    """

    isoformat = getattr(obj, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(obj)


def _clean(
    value: Any,
    *,
    strip_nulls: bool,
    strip_fields: frozenset[str],
) -> Any:
    if isinstance(value, dict):
        return {
            k: _clean(v, strip_nulls=strip_nulls, strip_fields=strip_fields)
            for k, v in value.items()
            if k not in strip_fields and (not strip_nulls or v is not None)
        }
    if isinstance(value, list):
        return [_clean(item, strip_nulls=strip_nulls, strip_fields=strip_fields) for item in value]
    return value
