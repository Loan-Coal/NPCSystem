"""
Module: pair_weighting
Layer: engines/gossip
Purpose: Pure function for computing faction-based gossip pair weight multiplier.
Does NOT: perform I/O or access graph state.
Dependencies injected: None.
"""

from __future__ import annotations


def compute_faction_weight(
    sharer_faction_ids: set[str],
    receiver_faction_ids: set[str],
    best_standing: int | None,
    same_faction_boost: float,
    allied_boost: float,
    hostile_penalty: float,
) -> float:
    """Return the faction multiplier for a gossip pair.

    Priority order (highest to lowest):
    1. Shared faction membership → same_faction_boost
    2. Allied standing (>= 50) → allied_boost
    3. Hostile standing (<= -50) → hostile_penalty
    4. Otherwise → 1.0

    Args:
        sharer_faction_ids: Set of active faction IDs the sharer belongs to.
        receiver_faction_ids: Set of active faction IDs the receiver belongs to.
        best_standing: Highest STANDS_WITH value from sharer factions toward receiver
            factions, or None if no standing edges exist.
        same_faction_boost: Multiplier when sharer and receiver share a faction.
        allied_boost: Multiplier when best_standing >= 50.
        hostile_penalty: Multiplier when best_standing <= -50.

    Returns:
        Float multiplier applied to the base gossip weight for this pair.
    """
    if sharer_faction_ids & receiver_faction_ids:
        return same_faction_boost
    if best_standing is not None and best_standing >= 50:
        return allied_boost
    if best_standing is not None and best_standing <= -50:
        return hostile_penalty
    return 1.0
