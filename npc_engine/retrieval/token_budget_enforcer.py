"""
token_budget_enforcer.py - Trims merged context to stay within a token budget.

Does NOT: fetch context or serialize output.

Dependencies injected: None.
"""

from retrieval.context_merger import ContextItem, MergedContext
from retrieval.context_utils import estimate_tokens
from utils.errors import TokenBudgetExceededError

__all__ = ["TokenBudgetExceededError", "enforce_budget"]

TIER0_MAX_TOKENS = 380


def enforce_budget(context: MergedContext, budget: int) -> MergedContext:
    """Trim tierB then tierA items to fit within the token budget while preserving tier0.

    Tier0 items are never dropped. tierA and tierB items are greedily retained in
    descending priority order until the remaining budget is exhausted.

    Args:
        context: Merged context to trim.
        budget: Maximum total token count across all retained items.

    Returns:
        A new MergedContext containing only items that fit within the budget.

    Raises:
        TokenBudgetExceededError: If tier0 items alone exceed the budget or the
            absolute TIER0_MAX_TOKENS cap.
    """

    tier0_items = [item for item in context.items if item.tier == "tier0"]
    tier_a_items = [item for item in context.items if item.tier == "tierA"]
    tier_b_items = [item for item in context.items if item.tier == "tierB"]

    tier0_tokens = sum(estimate_tokens(item.text) for item in tier0_items)
    if tier0_tokens > TIER0_MAX_TOKENS:
        raise TokenBudgetExceededError("Tier0 context exceeds fixed max token budget")
    if tier0_tokens > budget:
        raise TokenBudgetExceededError("Tier0 context exceeds token budget")

    remaining_budget = budget - tier0_tokens
    retained_a: list[ContextItem] = []
    retained_b: list[ContextItem] = []

    for item in sorted(tier_a_items, key=lambda value: value.priority, reverse=True):
        needed = estimate_tokens(item.text)
        if needed <= remaining_budget:
            retained_a.append(item)
            remaining_budget -= needed

    for item in sorted(tier_b_items, key=lambda value: value.priority, reverse=True):
        needed = estimate_tokens(item.text)
        if needed <= remaining_budget:
            retained_b.append(item)
            remaining_budget -= needed

    return MergedContext(items=[*tier0_items, *retained_a, *retained_b])
