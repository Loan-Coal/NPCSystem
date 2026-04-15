"""
context_merger.py - Combines retrieval tiers into a stable, deduplicated context object.

Does NOT: enforce token budget or serialize prompt text.

Dependencies injected: None.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ContextTier = Literal["tier0", "tierA", "tierB"]


class ContextItem(BaseModel):
    """One context item with tier and priority metadata."""

    key: str
    text: str
    tier: ContextTier
    priority: int

    model_config = ConfigDict(frozen=True)


class MergedContext(BaseModel):
    """Merged and ordered context items."""

    items: list[ContextItem] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


def merge_context(tier0: list[ContextItem], tier_a: list[ContextItem], tier_b: list[ContextItem]) -> MergedContext:
    """Merge context tiers with de-duplication by key and deterministic ordering."""

    merged_by_key: dict[str, ContextItem] = {}
    for item in [*tier0, *tier_a, *tier_b]:
        existing = merged_by_key.get(item.key)
        if existing is None or item.priority > existing.priority:
            merged_by_key[item.key] = item
    ordered = sorted(
        merged_by_key.values(),
        key=lambda item: (item.tier, -item.priority, item.key),
    )
    return MergedContext(items=ordered)
