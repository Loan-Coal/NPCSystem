"""
Module: context_builder_helpers
Layer: retrieval
Purpose: Pure helper functions used by context_builder to normalize values, trim serialized output,
    and apply retrieval quality lifts (query expansion, keyword re-ranking).
Does NOT: fetch graph/vector data, call LLM services, or enforce per-tier budgets.
Dependencies injected: None.
Used by: retrieval.context_builder
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from npc_engine.retrieval.context_merger import ContextItem, MergedContext
from npc_engine.retrieval.context_serializer import serialize_context
from npc_engine.retrieval.context_utils import estimate_tokens
from npc_engine.utils.errors import ContextBudgetError


def to_json_safe(value: Any) -> Any:
    """Recursively normalize runtime values to JSON-serializable primitives.

    Args:
        value: Any Python value that may contain datetime, Neo4j native types, dicts, or lists.

    Returns:
        A JSON-safe equivalent of value (str, int, float, bool, dict, list, or None).
    """

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [to_json_safe(item) for item in value]

    to_native = getattr(value, "to_native", None)
    if callable(to_native):
        try:
            return to_json_safe(to_native())
        except Exception:
            return str(value)

    return value


def normalize_ratio(value: float) -> float:
    """Clamp value to [0.0, 1.0].

    Args:
        value: Input float.

    Returns:
        Value clamped between 0.0 and 1.0 inclusive.
    """

    return max(0.0, min(1.0, value))


def enforce_final_serialized_budget_with_context(
    context: MergedContext,
    budget: int,
) -> tuple[MergedContext, str]:
    """Trim compressible tiers until the serialized prompt fits within the token budget.

    Args:
        context: Merged context to trim.
        budget: Maximum token count for the serialized prompt.

    Returns:
        Tuple of (final MergedContext, serialized JSON string).

    Raises:
        ContextBudgetError: If the prompt cannot fit within budget after all compressible items are dropped.
    """

    current = context
    while True:
        serialized = serialize_context(context=current)
        if estimate_tokens(serialized) <= budget:
            return current, serialized

        removable_candidates = [item for item in current.items if item.tier in {"tierC", "tierB"}]
        if len(removable_candidates) == 0:
            used_tokens = estimate_tokens(serialized)
            raise ContextBudgetError(
                tier="total_prompt",
                used_tokens=used_tokens,
                budget_tokens=budget,
                detail="Serialized context exceeds total prompt budget after compressible tier trimming.",
            )

        to_drop = sorted(
            removable_candidates,
            key=lambda item: (item.tier != "tierC", item.priority),
        )[0]
        current = current.model_copy(
            update={
                "items": [item for item in current.items if item.key != to_drop.key],
            }
        )


def expand_query(player_message: str, session_turns: list[str]) -> str:
    """Prepend last 2 session turns (content only, no speaker prefix) to player_message.

    Args:
        player_message: The current player message.
        session_turns: Accumulated turns in "speaker: text" format.

    Returns:
        Expanded query string for semantic search, or player_message unchanged when no history.
    """

    if len(session_turns) < 2:
        return player_message
    recent = [t.split(": ", 1)[-1] for t in session_turns[-2:]]
    return f"{' '.join(recent)} {player_message}".strip()


def keyword_overlap(text: str, query: str) -> float:
    """Fraction of query tokens present in text.

    Returns 0.0 for queries shorter than 2 tokens to avoid degenerate scoring.

    Args:
        text: Item text to score.
        query: Player message used as the query.

    Returns:
        Score in [0.0, 1.0]: proportion of query tokens found in text.
    """

    query_tokens = set(query.lower().split())
    if len(query_tokens) < 2:
        return 0.0
    text_tokens = set(text.lower().split())
    return len(query_tokens & text_tokens) / len(query_tokens)


def rerank_by_keyword(items: list[dict], field: str, query: str, top_k: int = 3) -> list[dict]:
    """Re-rank item dicts by keyword overlap of a text field against query, keep top_k.

    Args:
        items: List of dicts to re-rank.
        field: Key whose string value is compared against query.
        query: Player message used for overlap scoring.
        top_k: Number of top items to return after re-ranking.

    Returns:
        Up to top_k items ordered by descending keyword overlap.
    """

    return sorted(items, key=lambda item: keyword_overlap(item.get(field, ""), query), reverse=True)[:top_k]


def enforce_final_serialized_budget(context: MergedContext, budget: int) -> str:
    """Trim and serialize context to fit within budget.

    Args:
        context: Merged context to trim.
        budget: Maximum token count for the serialized prompt.

    Returns:
        Serialized JSON string within budget.
    """

    _, serialized = enforce_final_serialized_budget_with_context(context=context, budget=budget)
    return serialized
