"""
context_utils.py - Shared retrieval helpers for token estimation and key parsing.

Does NOT: enforce tier budgets or fetch graph/vector data.

Dependencies injected: None.
"""

from __future__ import annotations

import json
from typing import Any


CHARS_PER_TOKEN_ESTIMATE = 4


def estimate_tokens(text: str) -> int:
    """Approximate token count with a fixed chars-per-token heuristic.

    Args:
        text: Text to estimate token count for.

    Returns:
        Estimated token count; always at least 1.
    """

    return max(1, (len(text) + CHARS_PER_TOKEN_ESTIMATE - 1) // CHARS_PER_TOKEN_ESTIMATE)


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


def serialize_json(value: Any, *, compact: bool = False) -> str:
    """Serialize a value to JSON with deterministic key ordering.

    Args:
        value: JSON-serializable value to serialize.
        compact: When True, omits spaces around separators to minimize size.

    Returns:
        JSON string with ASCII encoding and sorted keys.
    """

    separators = (",", ":") if compact else None
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=separators)
