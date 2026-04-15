"""
token_budget_enforcer.py - Trims merged context to stay within a token budget.

Does NOT: fetch context or serialize output.

Dependencies injected: None.
"""

from retrieval.context_merger import ContextItem, MergedContext


CHARS_PER_TOKEN_ESTIMATE = 4
TIER0_MAX_TOKENS = 380


class TokenBudgetExceededError(Exception):
    """Raised when mandatory tier0 context alone exceeds budget."""



def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + CHARS_PER_TOKEN_ESTIMATE - 1) // CHARS_PER_TOKEN_ESTIMATE)



def enforce_budget(context: MergedContext, budget: int) -> MergedContext:
    """Trim tierB then tierA items while preserving tier0 items."""

    tier0_items = [item for item in context.items if item.tier == "tier0"]
    tier_a_items = [item for item in context.items if item.tier == "tierA"]
    tier_b_items = [item for item in context.items if item.tier == "tierB"]

    tier0_tokens = sum(_estimate_tokens(item.text) for item in tier0_items)
    if tier0_tokens > TIER0_MAX_TOKENS:
        raise TokenBudgetExceededError("Tier0 context exceeds fixed max token budget")
    if tier0_tokens > budget:
        raise TokenBudgetExceededError("Tier0 context exceeds token budget")

    remaining_budget = budget - tier0_tokens
    retained_a: list[ContextItem] = []
    retained_b: list[ContextItem] = []

    for item in sorted(tier_a_items, key=lambda value: value.priority, reverse=True):
        needed = _estimate_tokens(item.text)
        if needed <= remaining_budget:
            retained_a.append(item)
            remaining_budget -= needed

    for item in sorted(tier_b_items, key=lambda value: value.priority, reverse=True):
        needed = _estimate_tokens(item.text)
        if needed <= remaining_budget:
            retained_b.append(item)
            remaining_budget -= needed

    return MergedContext(items=[*tier0_items, *retained_a, *retained_b])
