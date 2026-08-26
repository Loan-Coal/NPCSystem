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
from .context_metrics import ContextDropReason
from .context_receipt import BudgetFillReport, DroppedItem
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
    "fill_to_budget_with_report",
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


# ISSUE-197 -- why tier A is sized from what tiers B and C leave behind.
#
# Tier A was capped at `min(tier_budget_tokens.tier_a, budget * tier_a_fraction)` whether or
# not the compressible tiers had anything to put in theirs. With no vector corpus they have
# nothing, so 45% of every prompt budget sat reserved for tiers spending zero while tier-A
# items were dropped for want of room. Measured live 2026-08-26: 564-742 tokens assembled
# against a 1,312-token budget, with beliefs, memories and goals competing for the remainder.
#
# Two bounds keep the reclaim safe in both directions:
#
#   FLOOR   -- when B and C are saturated tier A keeps exactly its configured fraction, so
#              the compressible tiers lose nothing. That is provable rather than incidental:
#              _fit_compressible_tier returns at most its own cap, so with both full the
#              leftover is `budget - tier0 - (0.30 + 0.15) * budget`, which sits below the
#              0.55 floor by precisely tier0. The A/B arms of P7 depend on this holding.
#   CEILING -- `tier_budget_tokens.tier_a` stays an absolute limit, as it was for the
#              fraction before it.
#
# This deliberately reserves NOTHING for JSON skeleton overhead. Measured, the item-token
# sum OVER-counts the serialized size more often than it under-counts, because the eight
# orphan keys (ISSUE-200) are charged in full here and contribute zero bytes to the output.
# The post-serialization trim loop stays the corrector; it measures the real thing.
def _tier_a_cap_with_reclaim(
    *,
    llm_config: LLMConfig,
    prompt_token_budget: int,
    tier0_tokens: int,
    compressed_b: list[ContextItem],
    compressed_c: list[ContextItem],
) -> int:
    """Return the tier-A soft cap, widened by whatever tiers B and C will not use.

    Args:
        llm_config: Per-engine config carrying tier budgets and fractions.
        prompt_token_budget: Total token budget for the serialized prompt.
        tier0_tokens: Tokens already committed by the always-pinned tier.
        compressed_b: Tier-B items AFTER compression -- what tier B will actually ask for.
        compressed_c: Tier-C items AFTER compression.
    Returns:
        Tier-A soft cap in tokens, never below the configured fraction of the budget and
        never above `tier_budget_tokens.tier_a`.
    """
    tier_a_fraction_floor = int(prompt_token_budget * llm_config.tier_a_fraction)
    committed = (
        tier0_tokens
        + sum(estimate_tokens(item.text) for item in compressed_b)
        + sum(estimate_tokens(item.text) for item in compressed_c)
    )
    return min(
        llm_config.tier_budget_tokens.tier_a,
        max(tier_a_fraction_floor, prompt_token_budget - committed),
    )


def _validated_tier0_tokens(items: list[ContextItem]) -> int:
    """Return tier-0's token total, or raise -- an oversized tier 0 is a data error."""
    tokens = sum(estimate_tokens(item.text) for item in items)
    if tokens > TIER0_MAX_TOKENS:
        raise ContextBudgetError(
            tier="tier0",
            used_tokens=tokens,
            budget_tokens=TIER0_MAX_TOKENS,
            detail="Tier 0 (world + emotion) exceeds non-compressible cap.",
        )
    return tokens


def _compressed_or_empty(
    *,
    tier_name: str,
    items: list[ContextItem],
    budget_tokens: int,
    llm_config: LLMConfig,
    cache: ContextCompressionCache,
) -> list[ContextItem]:
    """Compress a tier to its cap and sort it, yielding an empty tier rather than raising.

    fill_to_budget never fails a turn for budget reasons; a tier that cannot be compressed
    small enough is dropped whole, which is where the greedy fill would land anyway.
    """
    try:
        fitted = _fit_compressible_tier(
            tier_name=tier_name, items=items, budget_tokens=budget_tokens,
            llm_config=llm_config, cache=cache,
        )
    except ContextBudgetError:
        return []
    return sorted(fitted, key=lambda item: (-item.priority, item.key))


def _trim_to_serialized_budget(
    *, filled: MergedContext, prompt_token_budget: int
) -> tuple[MergedContext, str]:
    """Evict items until the REAL serialized JSON fits: tier C first, then B, then A.

    The greedy fill selects on a per-item token estimate; serialize_context reassembles a
    fixed skeleton, so estimate and truth differ in both directions. This is the only stage
    that measures the truth. Tier 0 and pinned items are never evicted (ISSUE-145), so a
    prompt of nothing but those is returned over budget rather than emptied.
    """
    from .context_serializer import serialize_context

    serialized = serialize_context(filled)
    while estimate_tokens(serialized) > prompt_token_budget:
        droppable = [i for i in filled.items if i.tier in TIER_DROP_ORDER and not i.pinned]
        if not droppable:
            break
        to_drop = sorted(droppable, key=lambda i: (TIER_DROP_ORDER[i.tier], i.priority))[0]
        filled = filled.model_copy(
            update={"items": [i for i in filled.items if i.key != to_drop.key]}
        )
        serialized = serialize_context(filled)
    return filled, serialized


def _attribute_drops(
    *,
    assembled: list[ContextItem],
    after_soft_caps: list[ContextItem],
    after_prompt_fill: list[ContextItem],
    survivors: list[ContextItem],
) -> tuple[DroppedItem, ...]:
    """Assign every item that did not reach the prompt to the stage that removed it.

    The three stages are strictly nested by key -- each one's output is a subset of its
    input -- so an item falls into exactly one bucket and the buckets cover every drop.
    Items outside TIER_DROP_ORDER are tier 0, which is never dropped.
    """
    stages: tuple[tuple[set[str], ContextDropReason], ...] = (
        ({i.key for i in after_soft_caps}, "tier_soft_cap"),
        ({i.key for i in after_prompt_fill}, "prompt_budget"),
        ({i.key for i in survivors}, "final_trim"),
    )
    dropped: list[DroppedItem] = []
    for item in assembled:
        if item.tier not in TIER_DROP_ORDER:
            continue
        for surviving_keys, reason in stages:
            if item.key not in surviving_keys:
                dropped.append(DroppedItem(key=item.key, tier=item.tier, reason=reason))
                break
    return tuple(dropped)


def _tier_b_soft_cap(*, llm_config: LLMConfig, prompt_token_budget: int) -> int:
    """Tier B's cap: the smaller of its configured budget and its fraction of the prompt.

    A function rather than a local so the compression pass and the greedy fill cannot
    drift apart on what tier B is allowed to spend.
    """
    return min(
        llm_config.tier_budget_tokens.tier_b,
        int(prompt_token_budget * llm_config.tier_b_fraction),
    )


def _compress_tiers_b_and_c(
    *,
    context: MergedContext,
    llm_config: LLMConfig,
    prompt_token_budget: int,
    cache: ContextCompressionCache,
) -> tuple[list[ContextItem], list[ContextItem]]:
    """Compress the two compressible tiers to their caps, priority-sorted.

    Runs before tier A is sized, which is what makes the reclaim possible: the leftover
    can only be computed once B and C have said what they actually need.
    """
    tier_c_fraction = max(0.0, 1.0 - llm_config.tier_a_fraction - llm_config.tier_b_fraction)
    tier_c_soft_cap = int(prompt_token_budget * tier_c_fraction)
    compressed_b = _compressed_or_empty(
        tier_name="tier_b",
        items=[i for i in context.items if i.tier == "tierB"],
        budget_tokens=_tier_b_soft_cap(
            llm_config=llm_config, prompt_token_budget=prompt_token_budget
        ),
        llm_config=llm_config,
        cache=cache,
    )
    compressed_c = _compressed_or_empty(
        tier_name="tier_c",
        items=[i for i in context.items if i.tier == "tierC"],
        budget_tokens=tier_c_soft_cap or llm_config.tier_budget_tokens.tier_c,
        llm_config=llm_config,
        cache=cache,
    )
    return compressed_b, compressed_c


def _greedy_fill(
    *,
    tier_a_fitted: list[ContextItem],
    compressed_b: list[ContextItem],
    compressed_c: list[ContextItem],
    tier0_tokens: int,
    llm_config: LLMConfig,
    prompt_token_budget: int,
) -> list[ContextItem]:
    """Select across tiers A, B and C against the one shared prompt budget.

    Tier order is the priority order: tier A commits first, then B, then C fills whatever
    is left. Each helper skips items that do not fit rather than stopping (ISSUE-145).
    """
    tier_a_selected, running = _fill_tier_a(
        items=tier_a_fitted,
        running_tokens=tier0_tokens,
        prompt_token_budget=prompt_token_budget,
    )
    tier_b_selected, running = _fill_capped_tier(
        items=compressed_b,
        running_tokens=running,
        prompt_token_budget=prompt_token_budget,
        tier_cap=_tier_b_soft_cap(
            llm_config=llm_config, prompt_token_budget=prompt_token_budget
        ),
    )
    tier_c_selected, _running = _fill_capped_tier(
        items=compressed_c,
        running_tokens=running,
        prompt_token_budget=prompt_token_budget,
        tier_cap=None,
    )
    return [*tier_a_selected, *tier_b_selected, *tier_c_selected]


def _fitted_tier_a(
    *,
    context: MergedContext,
    llm_config: LLMConfig,
    prompt_token_budget: int,
    tier0_tokens: int,
    compressed_b: list[ContextItem],
    compressed_c: list[ContextItem],
) -> list[ContextItem]:
    """Size tier A against the reclaimed cap, then apply the pinned-core + ranked-pool fill."""
    return _fit_tier_a_pinned_pool(
        items=[i for i in context.items if i.tier == "tierA"],
        budget_tokens=_tier_a_cap_with_reclaim(
            llm_config=llm_config,
            prompt_token_budget=prompt_token_budget,
            tier0_tokens=tier0_tokens,
            compressed_b=compressed_b,
            compressed_c=compressed_c,
        ),
    )


def fill_to_budget_with_report(
    *,
    context: MergedContext,
    llm_config: LLMConfig,
    prompt_token_budget: int,
    compression_cache: ContextCompressionCache | None = None,
) -> BudgetFillReport:
    """Fill context tiers greedily into prompt_token_budget, reporting every drop.

    The reporting variant of fill_to_budget, which documents the shared arguments. Same
    pass, with each excluded item attributed to the stage that excluded it. The comment
    above _tier_a_cap_with_reclaim explains how tier A is sized.

    Returns:
        A BudgetFillReport: the surviving context, its serialization, and the drops.
    Raises:
        ContextBudgetError: Only if tier0 alone exceeds TIER0_MAX_TOKENS (a data error).
    """
    cache = compression_cache or ContextCompressionCache()
    tier0_items = [i for i in context.items if i.tier == "tier0"]
    tier0_tokens = _validated_tier0_tokens(tier0_items)
    compressed_b, compressed_c = _compress_tiers_b_and_c(
        context=context, llm_config=llm_config,
        prompt_token_budget=prompt_token_budget, cache=cache)
    tier_a_fitted = _fitted_tier_a(
        context=context, llm_config=llm_config, prompt_token_budget=prompt_token_budget,
        tier0_tokens=tier0_tokens, compressed_b=compressed_b, compressed_c=compressed_c)
    after_prompt_fill = _greedy_fill(
        tier_a_fitted=tier_a_fitted, compressed_b=compressed_b, compressed_c=compressed_c,
        tier0_tokens=tier0_tokens, llm_config=llm_config,
        prompt_token_budget=prompt_token_budget)
    filled, serialized = _trim_to_serialized_budget(
        filled=MergedContext(items=[*tier0_items, *after_prompt_fill]),
        prompt_token_budget=prompt_token_budget)
    dropped = _attribute_drops(
        assembled=context.items, survivors=filled.items,
        after_soft_caps=[*tier_a_fitted, *compressed_b, *compressed_c],
        after_prompt_fill=after_prompt_fill)
    return BudgetFillReport(context=filled, serialized=serialized, dropped=dropped)


def fill_to_budget(
    *,
    context: MergedContext,
    llm_config: LLMConfig,
    prompt_token_budget: int,
    compression_cache: ContextCompressionCache | None = None,
) -> tuple[MergedContext, str]:
    """Fill context tiers greedily into prompt_token_budget.

    The report-free entry point every caller that only needs the filled context keeps
    using. A pure projection of fill_to_budget_with_report, so the two cannot diverge.

    Args:
        context: Merged context from all tiers.
        llm_config: Per-engine config providing tier budgets and fractions.
        prompt_token_budget: Total token budget for the serialized prompt.
        compression_cache: Optional cache for tier B/C field-selection compression.
    Returns:
        Tuple of (final MergedContext, serialized JSON string).
    Raises:
        ContextBudgetError: Only if tier0 alone exceeds TIER0_MAX_TOKENS (a data error).
    """
    report = fill_to_budget_with_report(
        context=context, llm_config=llm_config,
        prompt_token_budget=prompt_token_budget, compression_cache=compression_cache,
    )
    return report.context, report.serialized
