"""
context_merger.py - Combines retrieval tiers into a stable, deduplicated context object.
Layer: retrieval
Purpose: (auto-detected — review)

Does NOT: enforce token budget or serialize prompt text.

Dependencies injected: None.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ContextTier = Literal["tier0", "tierA", "tierB", "tierC"]


class ContextItem(BaseModel):
    """One context item with tier, priority, and pinned metadata.

    Pinned items are always included in the context output regardless of budget
    pressure. The enforcer includes all pinned items unconditionally and fills
    remaining budget from the non-pinned pool ordered by priority descending.
    """

    key: str
    text: str
    tier: ContextTier
    priority: int
    pinned: bool = False

    model_config = ConfigDict(frozen=True)


class MergedContext(BaseModel):
    """Merged and ordered context items."""

    items: list[ContextItem] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


def merge_context(
    tier0: list[ContextItem],
    tier_a: list[ContextItem],
    tier_b: list[ContextItem],
    tier_c: list[ContextItem] | None = None,
) -> MergedContext:
    """Merge context tiers with de-duplication by key and deterministic ordering.

    When the same key appears in multiple tiers, the item with the higher priority
    is retained. Items are ordered by (tier, -priority, key) for determinism.

    Args:
        tier0: Mandatory context items (world state, emotion).
        tier_a: High-priority graph-backed items (character, relations, events).
        tier_b: RAG-retrieved items (primary split).
        tier_c: RAG-retrieved items (secondary split); omitted if None.

    Returns:
        A frozen MergedContext with deduplicated, sorted items.
    """

    merged_by_key: dict[str, ContextItem] = {}
    for item in [*tier0, *tier_a, *tier_b, *(tier_c or [])]:
        existing = merged_by_key.get(item.key)
        if existing is None or item.priority > existing.priority:
            merged_by_key[item.key] = item
    ordered = sorted(
        merged_by_key.values(),
        key=lambda item: (item.tier, -item.priority, item.key),
    )
    return MergedContext(items=ordered)
