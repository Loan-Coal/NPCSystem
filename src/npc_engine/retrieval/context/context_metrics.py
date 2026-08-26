"""
context_metrics.py - Metric emission helpers for context assembly.
Layer: retrieval
Purpose: Metric emission helpers for context assembly.

Does NOT: retrieve or modify context items.

Dependencies injected: None.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

from .context_compression import COMPRESSION_SUFFIX
from .context_merger import MergedContext
from .context_utils import estimate_tokens
from npc_engine.utils.metrics import increment_metric


CONTEXT_ITEMS_SELECTED_METRIC = "context_items_selected_total"
CONTEXT_TIER_TOKENS_METRIC = "context_tier_tokens"
CONTEXT_BUDGET_ERRORS_METRIC = "context_budget_errors_total"
CONTEXT_ITEMS_DROPPED_METRIC = "context_items_dropped_total"
LLM_COMPRESSIONS_METRIC = "llm_compressions_total"
CONTEXT_CACHE_HITS_METRIC = "dialogue_context_cache_hits_total"
CONTEXT_CACHE_MISSES_METRIC = "dialogue_context_cache_misses_total"

ContextDropReason = Literal["tier_soft_cap", "prompt_budget", "final_trim"]
"""Why a context item did not reach the prompt.

tier_soft_cap: excluded by a per-tier budget before the global fill.
prompt_budget: excluded by the total prompt token budget during the greedy fill.
final_trim: dropped after serialization when the real JSON exceeded the budget.
"""

_NEVER_DROPPED_TIER = "tier0"


class _AttributedDrop(Protocol):
    """The shape record_attributed_drop_metrics reads off a DroppedItem.

    Structural rather than a concrete import: context_receipt imports ContextDropReason
    from this module, so importing DroppedItem back would close a cycle.
    """

    @property
    def tier(self) -> str: ...

    @property
    def reason(self) -> ContextDropReason: ...


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


def record_attributed_drop_metrics(drops: Sequence[_AttributedDrop]) -> None:
    """Emit one counter per (tier, reason) pair over already-attributed drops.

    Without this, budget starvation is silent — the failure mode behind ISSUE-145, where
    pinned items were dropped with no exception, log, or metric. Until P4 every drop was
    reported as `prompt_budget` regardless of which stage removed it, so `tier_soft_cap`
    and `final_trim` were declared above and never emitted by anything.

    Args:
        drops: Attributed drops from fill_to_budget_with_report.
    """

    counts: dict[tuple[str, str], int] = {}
    for drop in drops:
        if drop.tier == _NEVER_DROPPED_TIER:
            continue
        counts[(drop.tier, drop.reason)] = counts.get((drop.tier, drop.reason), 0) + 1

    for (tier, reason), count in counts.items():
        increment_metric(
            metric=CONTEXT_ITEMS_DROPPED_METRIC,
            amount=float(count),
            labels={"tier": tier.lower(), "reason": reason},
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
