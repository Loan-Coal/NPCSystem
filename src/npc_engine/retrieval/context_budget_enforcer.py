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
from npc_engine.schema.llm_config_models import LLMConfig
from npc_engine.utils.errors import ContextBudgetError

__all__ = [
    "ContextBudgetError",
    "ContextCompressionCache",
    "COMPRESSION_SUFFIX",
    "build_compression_cache_key",
    "enforce_context_budget",
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

    cache = compression_cache or ContextCompressionCache()

    tier0_items = [item for item in context.items if item.tier == "tier0"]
    tier_a_items = [item for item in context.items if item.tier == "tierA"]
    tier_b_items = [item for item in context.items if item.tier == "tierB"]
    tier_c_items = [item for item in context.items if item.tier == "tierC"]

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
