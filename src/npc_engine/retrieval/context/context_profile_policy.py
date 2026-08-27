"""
Module: context_profile_policy
Layer: retrieval
Purpose: Apply a RetrievalProfile's ASSEMBLY knobs — enabled_tiers, disabled_slots and
         slot_cap_overrides — to the raw context items before ranking.
Does NOT: fetch anything, rank, serialize, or read Settings.
Dependencies injected: the profile, the llm_config and the compression cache.
Used by: retrieval.context.context_builder.

The rule this module exists to hold
-----------------------------------
Assembly may vary between arms. SCHEMA MUST NOT. Nothing here touches the serializer: it
filters and caps ITEMS, and the generated serializer goes on emitting every declared slot
with its empty default. Two arms whose JSON differs in shape are measuring schema drift,
not retrieval.
"""

from __future__ import annotations

from typing import Any

from npc_engine.schema.retrieval_profile_models import RetrievalProfile

from .context_merger import ContextItem
from .context_slots import slot_for_key
from .context_utils import estimate_tokens

__all__ = ["apply_slot_policy", "tier_enabled"]


def tier_enabled(profile: RetrievalProfile, tier: str) -> bool:
    """Return whether this arm assembles the given tier at all.

    Args:
        profile: The resolved profile for this turn.
        tier: One of tier0, tierA, tierB, tierC.
    Returns:
        True when the tier should be fetched, ranked and charged.
    """
    return tier in profile.enabled_tiers


def _slot_key_for(item: ContextItem) -> str | None:
    slot = slot_for_key(item.key)
    return slot.key if slot is not None else None


def _capped(
    item: ContextItem, cap: int, llm_config: Any, compression_cache: Any
) -> ContextItem:
    """Return the item compressed to `cap` tokens, or unchanged when already under it."""
    if estimate_tokens(item.text) <= cap:
        return item
    compressed = compression_cache.compress_item(
        item=item, llm_config=llm_config, target_tokens=cap
    )
    return item.model_copy(update={"text": compressed})


def apply_slot_policy(
    items: list[ContextItem],
    *,
    profile: RetrievalProfile,
    llm_config: Any,
    compression_cache: Any,
) -> list[ContextItem]:
    """Drop this arm's disabled slots and cap its overridden ones.

    Applied BEFORE ranking, deliberately: a cap enforced after selection would let one
    fat slot win the budget and then shrink, which changes what the OTHER slots got.

    Args:
        items: Raw context items from the producers, in production order.
        profile: The resolved profile for this turn.
        llm_config: Config carrying the compression cache versions.
        compression_cache: Cache used to shrink an over-cap item.
    Returns:
        A new list, in the same order, minus disabled slots and with caps applied.
    """
    if not profile.disabled_slots and not profile.slot_cap_overrides:
        return items
    kept: list[ContextItem] = []
    for item in items:
        slot_key = _slot_key_for(item)
        if slot_key is not None and slot_key in profile.disabled_slots:
            continue
        cap = profile.slot_cap_overrides.get(slot_key) if slot_key is not None else None
        kept.append(item if cap is None else _capped(item, cap, llm_config, compression_cache))
    return kept
