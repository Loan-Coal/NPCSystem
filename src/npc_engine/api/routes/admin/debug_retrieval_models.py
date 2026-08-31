"""
Module: debug_retrieval_models
Layer: api
Purpose: Response models for GET /v1/admin/debug/retrieval, plus the parse of the
         serialized context blob into its top-level slots.
Does NOT: call the retrieval pipeline, perform auth, or read Settings.
Dependencies injected: none — every input is a function argument.
Used by: api.routes.admin.debug_retrieval (the route handler).

Split out of debug_retrieval.py because P9 grew that module past its useful size and the
300-line cap is a hard limit. The two halves are a clean split: this file answers "what
shape does the probe return", the other answers "what does the probe run".
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

from npc_engine.retrieval.context.context_receipt import ContextReceipt

__all__ = [
    "ContextItemView",
    "DebugRetrievalResponse",
    "parse_context_items",
]

_UNKNOWN_TIER = "unknown"
_DEFAULT_PRIORITY = 0


class ContextItemView(BaseModel):
    """One parsed context SLOT from the serialized prompt blob.

    A slot is not an item. `build_serialized_context` reparses ranked items into a fixed
    skeleton, so tier and priority are not recoverable here and are set to sentinels.
    Read `DebugRetrievalResponse.context_receipt` for per-ITEM keys and per-tier spend;
    this view remains because it is the shape every pre-P9 caller reads.
    """

    key: str
    tier: str
    priority: int
    text: str

    model_config = ConfigDict(frozen=True)


class DebugRetrievalResponse(BaseModel):
    """Response body for GET /debug/retrieval.

    Attributes:
        npc_id: The NPC whose retrieval context was built.
        query: The player query used as the retrieval signal.
        player_id: The player the context was assembled FOR, echoed back. None means the
            probe ran without one, in which case the three reputation slots are
            structurally empty and must not be read as "this NPC has no reputation".
        retrieval_profile: Resolved arm name this assembly ran under.
        context_items: Parsed top-level slots from the serialized context.
        context_receipt: What actually reached the model — item keys, per-tier spend and
            attributed drops. None on a legacy-cache hit, where assembly was
            short-circuited and there is genuinely nothing to report (DEC-195).
        total_tokens: Estimated token count of the serialized context blob.
    """

    npc_id: str
    query: str
    player_id: str | None = None
    retrieval_profile: str = ""
    context_items: list[ContextItemView]
    context_receipt: ContextReceipt | None = None
    total_tokens: int

    model_config = ConfigDict(frozen=True)


def parse_context_items(serialized: str) -> list[ContextItemView]:
    """Parse the serialized context blob into a flat list of ContextItemView entries.

    Args:
        serialized: JSON string returned by the context builder.

    Returns:
        One entry per top-level key in the JSON object. Empty when the object is empty,
        the string is blank, or the payload is not a JSON object.
    """
    if not serialized:
        return []
    try:
        parsed = json.loads(serialized)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    return [
        ContextItemView(
            key=key,
            tier=_UNKNOWN_TIER,
            priority=_DEFAULT_PRIORITY,
            text=value if isinstance(value, str) else json.dumps(value, ensure_ascii=False),
        )
        for key, value in parsed.items()
    ]
