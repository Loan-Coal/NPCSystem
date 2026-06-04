"""
context_metrics.py - Metric emission helpers for context assembly.
Layer: retrieval
Purpose: (auto-detected — review)

Does NOT: retrieve or modify context items.

Dependencies injected: None.
"""

from __future__ import annotations

from npc_engine.retrieval.context_compression import COMPRESSION_SUFFIX
from npc_engine.retrieval.context_merger import MergedContext
from npc_engine.retrieval.context_utils import estimate_tokens
from npc_engine.utils.metrics import increment_metric


CONTEXT_ITEMS_SELECTED_METRIC = "context_items_selected_total"
CONTEXT_TIER_TOKENS_METRIC = "context_tier_tokens"
CONTEXT_BUDGET_ERRORS_METRIC = "context_budget_errors_total"
LLM_COMPRESSIONS_METRIC = "llm_compressions_total"
CONTEXT_CACHE_HITS_METRIC = "dialogue_context_cache_hits_total"
CONTEXT_CACHE_MISSES_METRIC = "dialogue_context_cache_misses_total"


def record_context_metrics(context: MergedContext) -> None:
    """Emit item-count and token-count metrics for each context tier.

    Args:
        context: Merged context after budget enforcement.
    """

    for tier in ("tier0", "tierA", "tierB", "tierC"):
        tier_items = [item for item in context.items if item.tier == tier]
        tier_count = len(tier_items)
        tier_tokens = sum(estimate_tokens(item.text) for item in tier_items)
        if tier_count > 0:
            increment_metric(
                metric=CONTEXT_ITEMS_SELECTED_METRIC,
                amount=float(tier_count),
                labels={"tier": tier.lower()},
            )
        increment_metric(
            metric=CONTEXT_TIER_TOKENS_METRIC,
            amount=float(tier_tokens),
            labels={"tier": tier.lower()},
        )


def record_compression_metrics(pre_budget_context: MergedContext, post_budget_context: MergedContext) -> None:
    """Emit compression count metric when budget enforcement compresses any items.

    Args:
        pre_budget_context: Merged context before budget enforcement.
        post_budget_context: Merged context after budget enforcement.
    """

    pre_budget_map = {item.key: item.text for item in pre_budget_context.items}
    compressed_count = sum(
        1
        for item in post_budget_context.items
        if item.key in pre_budget_map
        and item.text != pre_budget_map[item.key]
        and COMPRESSION_SUFFIX in item.text
    )
    if compressed_count > 0:
        increment_metric(metric=LLM_COMPRESSIONS_METRIC, amount=float(compressed_count), labels={"engine": "dialogue"})
