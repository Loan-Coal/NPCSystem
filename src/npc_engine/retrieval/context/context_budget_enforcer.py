"""
Module: context_budget_enforcer
Layer: retrieval
Purpose: Tier-aware context budget enforcement — pinned-core + ranked-pool for tier A;
         compression and drop for tiers B/C.
Does NOT: call LLM services; perform graph queries; emit metrics.
Dependencies injected: LLMConfig via parameter; ContextCompressionCache (optional).
Used by: retrieval.context_builder
"""

from __future__ import annotations

from .context_compression import (
    COMPRESSION_SUFFIX,
    ContextCompressionCache,
    build_compression_cache_key,
)
from .context_merger import ContextItem, MergedContext
from .context_utils import estimate_tokens
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

TIER0_MAX_TOKENS = 380
"""Fixed tier0 ceiling. Exceeding it is a data error, not a budget-pressure condition."""

TIER_DROP_ORDER: dict[str, int] = {"tierA": 2, "tierB": 1, "tierC": 0}
"""Post-serialization drop precedence: lower value is dropped first (tier C before A)."""


def enforce_context_budget(
    *,
    context: MergedContext,
    llm_config: LLMConfig,
    compression_cache: ContextCompressionCache | None = None,
) -> MergedContext:
    """Apply tier-aware budget policy with compression for compressible tiers.

    Tier 0 is always included and validated against TIER0_MAX_TOKENS (data error if exceeded).
    Tier A uses pinned-core + ranked-pool fill: pinned items are always included; the
    remaining budget is filled from non-pinned pool ordered by priority descending.
    Tiers B and C are compressed and/or dropped to fit their configured budgets.

    Args:
        context: Merged context to enforce budgets on.
        llm_config: LLM configuration carrying per-tier token budgets and compression settings.
        compression_cache: Optional pre-warmed compression cache; a new cache is created if omitted.

    Returns:
        A new MergedContext with tier A trimmed to budget and tier B/C compressed or dropped.

    Raises:
        ContextBudgetError: Only if tier0 exceeds TIER0_MAX_TOKENS or session turns exceed
            their sub-budget (both are data errors, not pool-overflow conditions).
    """


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

    session_items = [item for item in tier_a_items if item.key == "session"]
    session_tokens = sum(estimate_tokens(item.text) for item in session_items)
    if session_tokens > llm_config.session_turns_budget_tokens:
        raise ContextBudgetError(
            tier="session_turns",
            used_tokens=session_tokens,
            budget_tokens=llm_config.session_turns_budget_tokens,
            detail="Session turns exceed Tier A sub-budget and are non-compressible.",
        )

    tier_a_fitted = _fit_tier_a_pinned_pool(
        items=tier_a_items,
        budget_tokens=llm_config.tier_budget_tokens.tier_a,
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

    return MergedContext(items=[*tier0_items, *tier_a_fitted, *tier_b_fitted, *tier_c_fitted])


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


def _fit_tier_a_pinned_pool(
    *,
    items: list[ContextItem],
    budget_tokens: int,
) -> list[ContextItem]:
    """Apply pinned-core + ranked-pool policy to a tier-A item list.

    Pinned items are always included regardless of budget. The remaining budget
    is filled from non-pinned items sorted by priority descending (lowest priority
    dropped first when budget is exceeded).

    Args:
        items: All tier-A ContextItems to consider.
        budget_tokens: Maximum tokens allowed for the returned tier-A list.

    Returns:
        Filtered list containing all pinned items plus as many non-pinned items
        as fit within the remaining budget, ordered by priority descending.
    """
    pinned = [item for item in items if item.pinned]
    non_pinned = sorted(
        [item for item in items if not item.pinned],
        key=lambda item: (-item.priority, item.key),
    )
    pinned_tokens = sum(estimate_tokens(item.text) for item in pinned)
    remaining = budget_tokens - pinned_tokens
    selected_non_pinned: list[ContextItem] = []
    for item in non_pinned:
        tok = estimate_tokens(item.text)
        if remaining - tok < 0:
            # Skip, do not stop: smaller lower-priority items behind this one may fit.
            continue
        selected_non_pinned.append(item)
        remaining -= tok
    return [*pinned, *selected_non_pinned]


def _fill_tier_a(
    *,
    items: list[ContextItem],
    running_tokens: int,
    prompt_token_budget: int,
) -> tuple[list[ContextItem], int]:
    """Select tier-A items against the total prompt budget.

    Pinned items are appended unconditionally — the pinned-core contract guarantees
    they reach the prompt regardless of budget pressure (ISSUE-145). Non-pinned items
    that do not fit are skipped rather than terminating the scan, so smaller
    lower-priority items behind them are still considered.

    Args:
        items: Tier-A items in selection order (pinned first, then priority descending).
        running_tokens: Tokens already committed by preceding tiers.
        prompt_token_budget: Total token budget for the serialized prompt.
    Returns:
        Tuple of (selected items, updated running token count).
    """
    selected: list[ContextItem] = []
    running = running_tokens
    for item in items:
        tokens = estimate_tokens(item.text)
        if not item.pinned and running + tokens > prompt_token_budget:
            continue
        selected.append(item)
        running += tokens
    return selected, running


def _fill_capped_tier(
    *,
    items: list[ContextItem],
    running_tokens: int,
    prompt_token_budget: int,
    tier_cap: int | None,
) -> tuple[list[ContextItem], int]:
    """Select compressible-tier items within both the tier soft cap and the prompt budget.

    Items that do not fit are skipped rather than terminating the scan.

    Args:
        items: Tier items in priority-descending order.
        running_tokens: Tokens already committed by preceding tiers.
        prompt_token_budget: Total token budget for the serialized prompt.
        tier_cap: Per-tier soft cap, or None for no tier-level cap.
    Returns:
        Tuple of (selected items, updated running token count).
    """
    selected: list[ContextItem] = []
    running = running_tokens
    tier_running = 0
    for item in items:
        tokens = estimate_tokens(item.text)
        if tier_cap is not None and tier_running + tokens > tier_cap:
            continue
        if running + tokens > prompt_token_budget:
            continue
        selected.append(item)
        tier_running += tokens
        running += tokens
    return selected, running


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
    from .context_serializer import serialize_context

    cache = compression_cache or ContextCompressionCache()

    tier0_items = [item for item in context.items if item.tier == "tier0"]
    tier_a_items_raw = [item for item in context.items if item.tier == "tierA"]
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

    # Tier A: pinned items always included; remaining budget filled from non-pinned pool.
    tier_a_fitted = _fit_tier_a_pinned_pool(
        items=tier_a_items_raw,
        budget_tokens=tier_a_soft_cap,
    )
    tier_a_selected, running = _fill_tier_a(
        items=tier_a_fitted,
        running_tokens=running,
        prompt_token_budget=prompt_token_budget,
    )
    tier_b_selected, running = _fill_capped_tier(
        items=compressed_b_sorted,
        running_tokens=running,
        prompt_token_budget=prompt_token_budget,
        tier_cap=tier_b_soft_cap,
    )
    tier_c_selected, running = _fill_capped_tier(
        items=compressed_c_sorted,
        running_tokens=running,
        prompt_token_budget=prompt_token_budget,
        tier_cap=None,
    )

    filled = MergedContext(
        items=[*selected, *tier_a_selected, *tier_b_selected, *tier_c_selected]
    )

    # Verify actual serialized size (corrects for JSON skeleton overhead) and trim if needed.
    serialized = serialize_context(filled)
    while estimate_tokens(serialized) > prompt_token_budget:
        droppable = [item for item in filled.items if item.tier != "tier0" and not item.pinned]
        if not droppable:
            break  # only tier0 and pinned items remain; return as-is
        # Drop from tier_c first, then tier_b, then tier_a — lowest priority first within each.
        to_drop = sorted(
            droppable,
            key=lambda i: (TIER_DROP_ORDER[i.tier], i.priority),
        )[0]
        filled = filled.model_copy(
            update={"items": [i for i in filled.items if i.key != to_drop.key]}
        )
        serialized = serialize_context(filled)

    return filled, serialized
