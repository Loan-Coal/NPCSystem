"""
context_utils.py - Shared retrieval helpers for token estimation and key parsing.
Layer: retrieval
Purpose: Shared retrieval helpers for token estimation and key parsing.

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

NON_PROMPT_NODE_FIELDS: frozenset[str] = frozenset({
    # Machine state — carries no dialogue signal and is ruinously expensive.
    "embedding",
    # Graph bookkeeping — wall-clock timestamps the NPC cannot reason about.
    "created_at",
    "updated_at",
    "last_updated_at",
    "last_graph_updated_at",
    "last_embedding_indexed_at",
    "schema_version",
    # Wall-clock-derived ticks. dialogue_handler stamps writes with
    # int(datetime.now().timestamp()), so these change on every call and are the
    # single largest source of prompt non-determinism (EVAL-P20.0 / DEC-176).
    # `expires_at_tick` is stripped wherever it appears as a real key. NOTE it does NOT
    # reach the one inside `routine_override`: that property is persisted as an opaque
    # JSON *string*, so _clean walks past it and both keys survive into the prompt --
    # verified live 2026-08-26 (ISSUE-207). The entry is still correct for every producer
    # that emits the key structurally.
    "emotion_updated_at_tick",
    "expires_at_tick",
    # Lifecycle flags used by readers, not by dialogue.
    "is_active",
    "is_player",
    # Audit trail on the RELATES_TO edge: one record per relation mutation, each with a
    # wall-clock `timestamp` and a `tick_id`. Read only by mutation/ for rolling-window
    # bounds. It duplicates values the edge already carries as trust/fear/affection, and
    # measured 1,680 chars (~420 tokens) on a 6-interaction relation -- most of the
    # ~505-token `relation:player` item that ISSUE-199 measured.
    "delta_log",
})
"""Node properties that must never be serialized into an LLM prompt.

Measured on the live stack 2026-08-14: the 384-float `embedding` vector alone rendered
as 2,014 tokens inside a single pinned character profile — 90% of that profile and
3.9x the entire 512-token PROMPT_TOKEN_BUDGET. Graph readers return `properties(n)`
wholesale, so anything not stripped here is paid for in prompt tokens.

The wall-clock entries carry a second cost, measured 2026-08-14 during EVAL-P20.0: of
145 eval records whose only between-run difference was `world.last_updated_at` plus
`emotion_updated_at_tick`, **36 of 36 produced different npc_response text**. Fields
that carry no dialogue signal were on their own sufficient to destroy reproducibility —
and with it ~81% of the 393 human labels at every regeneration. This set is the
enforcement point for CLAUDE.md's strict "Idempotent assembly" rule; apply it to
*every* payload serialized into prompt content, not only character nodes.
"""


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
