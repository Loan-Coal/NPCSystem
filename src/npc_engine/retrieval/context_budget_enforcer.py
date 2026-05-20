"""
context_budget_enforcer.py - Tier-aware context budget enforcement with compression cache.

Does NOT: call external LLM services for compression.

Dependencies injected: LLMConfig.
"""

from __future__ import annotations

from npc_engine.retrieval.context_compression import (
    COMPRESSION_SUFFIX,
    ContextCompressionCache,
    build_compression_cache_key,
)
from npc_engine.retrieval.context_merger import ContextItem, MergedContext
from npc_engine.retrieval.context_utils import estimate_tokens
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.utils.errors import ContextBudgetError

__all__ = [
    "ContextBudgetError",
    "ContextCompressionCache",
    "COMPRESSION_SUFFIX",
    "build_compression_cache_key",
    "enforce_context_budget",
    "fill_to_budget",
]


def enforce_context_budget(
    *,
    context: MergedContext,
    llm_config: LLMConfig,
    compression_cache: ContextCompressionCache | None = None,
) -> MergedContext:
    """Apply tier-aware budget policy with compression for compressible tiers.

    Tier A is validated against a hard token budget and is not compressed.
    Tiers B and C are compressed and/or dropped to fit their configured budgets.

    Args:
        context: Merged context to enforce budgets on.
        llm_config: LLM configuration carrying per-tier token budgets and compression settings.
        compression_cache: Optional pre-warmed compression cache; a new cache is created if omitted.

    Returns:
        A new MergedContext with tier B/C items compressed or dropped to satisfy budgets.

    Raises:
        ContextBudgetError: If tier A or session-turns exceed their non-compressible budgets,
            or if a compressible tier cannot fit within budget after compression and dropping.
    """

    TIER0_MAX_TOKENS = 380  # matches legacy token_budget_enforcer constant

    cache = compression_cache or ContextCompressionCache()

    tier0_items = [item for item in context.items if item.tier == "tier0"]
    tier_a_items = [item for item in context.items if item.tier == "tierA"]
    tier_b_items = [item for item in context.items if item.tier == "tierB"]
    tier_c_items = [item for item in context.items if item.tier == "tierC"]

    tier0_tokens = sum(estimate_tokens(item.text) for item in tier0_items)
    if tier0_tokens > TIER0_MAX_TOKENS:
        raise ContextBudgetError(
            tier="tier0",
            used_tokens=tier0_tokens,
            budget_tokens=TIER0_MAX_TOKENS,
            detail="Tier 0 (world + emotion) exceeds non-compressible cap.",
        )

    tier_a_tokens = sum(estimate_tokens(item.text) for item in tier_a_items)
    tier_a_budget = llm_config.tier_budget_tokens.tier_a
    if tier_a_tokens > tier_a_budget:
        raise ContextBudgetError(
            tier="tier_a",
            used_tokens=tier_a_tokens,
            budget_tokens=tier_a_budget,
            detail="Tier A exceeds configured budget and is non-compressible.",
        )

    session_items = [item for item in tier_a_items if item.key == "session"]
    session_tokens = sum(estimate_tokens(item.text) for item in session_items)
    if session_tokens > llm_config.session_turns_budget_tokens:
        raise ContextBudgetError(
            tier="session_turns",
            used_tokens=session_tokens,
            budget_tokens=llm_config.session_turns_budget_tokens,
            detail="Session turns exceed Tier A sub-budget and are non-compressible.",
        )

    tier_b_fitted = _fit_compressible_tier(
        tier_name="tier_b",
        items=tier_b_items,
        budget_tokens=llm_config.tier_budget_tokens.tier_b,
        llm_config=llm_config,
        cache=cache,
    )
    tier_c_fitted = _fit_compressible_tier(
        tier_name="tier_c",
        items=tier_c_items,
        budget_tokens=llm_config.tier_budget_tokens.tier_c,
        llm_config=llm_config,
        cache=cache,
    )

    return MergedContext(items=[*tier0_items, *tier_a_items, *tier_b_fitted, *tier_c_fitted])


def _fit_compressible_tier(
    *,
    tier_name: str,
    items: list[ContextItem],
    budget_tokens: int,
    llm_config: LLMConfig,
    cache: ContextCompressionCache,
) -> list[ContextItem]:
    if len(items) == 0:
        return []

    used_tokens = sum(estimate_tokens(item.text) for item in items)
    if used_tokens <= budget_tokens and used_tokens <= int(budget_tokens * llm_config.compression_trigger_ratio):
        return items

    per_item_target = max(1, budget_tokens // len(items))
    compressed_items = [
        item.model_copy(
            update={
                "text": cache.compress_item(item=item, llm_config=llm_config, target_tokens=per_item_target),
            }
        )
        for item in items
    ]

    fitted = sorted(compressed_items, key=lambda item: (-item.priority, item.key))
    total_tokens = sum(estimate_tokens(item.text) for item in fitted)

    while total_tokens > budget_tokens and len(fitted) > 0:
        dropped = fitted.pop()
        total_tokens -= estimate_tokens(dropped.text)

    if total_tokens > budget_tokens:
        raise ContextBudgetError(
            tier=tier_name,
            used_tokens=total_tokens,
            budget_tokens=budget_tokens,
            detail="Tier exceeds budget after compression.",
        )

    return fitted


TIER0_MAX_TOKENS = 380


def fill_to_budget(
    *,
    context: MergedContext,
    llm_config: LLMConfig,
    prompt_token_budget: int,
    compression_cache: ContextCompressionCache | None = None,
) -> tuple[MergedContext, str]:
    """Fill context tiers greedily into prompt_token_budget.

    Tier0 is always included. Tier A, B, C are filled in priority order up to
    their per-engine soft caps (derived as fractions of prompt_token_budget).
    When budget is tight, lower-priority items are dropped: tier_c first, then
    tier_b, then tier_a. Never raises ContextBudgetError for budget reasons.

    Args:
        context: Merged context from all tiers.
        llm_config: Per-engine config providing tier budgets and fractions.
        prompt_token_budget: Total token budget for the serialized prompt.
        compression_cache: Optional cache for tier B/C field-selection compression.

    Returns:
        Tuple of (final MergedContext, serialized JSON string).

    Raises:
        ContextBudgetError: Only if tier0 alone exceeds TIER0_MAX_TOKENS (data error).
    """
    from npc_engine.retrieval.context_serializer import serialize_context

    cache = compression_cache or ContextCompressionCache()

    tier0_items = [item for item in context.items if item.tier == "tier0"]
    tier_a_items = sorted(
        [item for item in context.items if item.tier == "tierA"],
        key=lambda i: (-i.priority, i.key),
    )
    tier_b_items = [item for item in context.items if item.tier == "tierB"]
    tier_c_items = [item for item in context.items if item.tier == "tierC"]

    tier0_tokens = sum(estimate_tokens(item.text) for item in tier0_items)
    if tier0_tokens > TIER0_MAX_TOKENS:
        raise ContextBudgetError(
            tier="tier0",
            used_tokens=tier0_tokens,
            budget_tokens=TIER0_MAX_TOKENS,
            detail="Tier 0 (world + emotion) exceeds non-compressible cap.",
        )

    # Soft caps: smallest of the per-tier config budget and the fraction-derived budget.
    tier_a_soft_cap = min(
        llm_config.tier_budget_tokens.tier_a,
        int(prompt_token_budget * llm_config.tier_a_fraction),
    )
    tier_b_soft_cap = min(
        llm_config.tier_budget_tokens.tier_b,
        int(prompt_token_budget * llm_config.tier_b_fraction),
    )

    # Compress tier_b and tier_c to their soft caps before greedy fill.
    try:
        compressed_b = _fit_compressible_tier(
            tier_name="tier_b",
            items=tier_b_items,
            budget_tokens=tier_b_soft_cap,
            llm_config=llm_config,
            cache=cache,
        )
    except ContextBudgetError:
        compressed_b = []

    tier_c_soft_cap = int(prompt_token_budget * max(0.0, 1.0 - llm_config.tier_a_fraction - llm_config.tier_b_fraction))
    try:
        compressed_c = _fit_compressible_tier(
            tier_name="tier_c",
            items=tier_c_items,
            budget_tokens=tier_c_soft_cap if tier_c_soft_cap > 0 else llm_config.tier_budget_tokens.tier_c,
            llm_config=llm_config,
            cache=cache,
        )
    except ContextBudgetError:
        compressed_c = []

    compressed_b_sorted = sorted(compressed_b, key=lambda i: (-i.priority, i.key))
    compressed_c_sorted = sorted(compressed_c, key=lambda i: (-i.priority, i.key))

    # Greedy fill using estimated token counts per item.
    selected: list[ContextItem] = list(tier0_items)
    running = tier0_tokens

    tier_a_running = 0
    for item in tier_a_items:
        tok = estimate_tokens(item.text)
        if tier_a_running + tok > tier_a_soft_cap:
            break
        if running + tok > prompt_token_budget:
            break
        selected.append(item)
        tier_a_running += tok
        running += tok

    tier_b_running = 0
    for item in compressed_b_sorted:
        tok = estimate_tokens(item.text)
        if tier_b_running + tok > tier_b_soft_cap:
            break
        if running + tok > prompt_token_budget:
            break
        selected.append(item)
        tier_b_running += tok
        running += tok

    for item in compressed_c_sorted:
        tok = estimate_tokens(item.text)
        if running + tok > prompt_token_budget:
            break
        selected.append(item)
        running += tok

    filled = MergedContext(items=selected)

    # Verify actual serialized size (corrects for JSON skeleton overhead) and trim if needed.
    serialized = serialize_context(filled)
    while estimate_tokens(serialized) > prompt_token_budget:
        droppable = [item for item in filled.items if item.tier != "tier0"]
        if not droppable:
            break  # only tier0 remains; return as-is
        # Drop from tier_c first, then tier_b, then tier_a — lowest priority first within each.
        to_drop = sorted(
            droppable,
            key=lambda i: ({"tierA": 2, "tierB": 1, "tierC": 0}[i.tier], i.priority),
        )[0]
        filled = filled.model_copy(
            update={"items": [i for i in filled.items if i.key != to_drop.key]}
        )
        serialized = serialize_context(filled)

    return filled, serialized
