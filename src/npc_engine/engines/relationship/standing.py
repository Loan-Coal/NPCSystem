"""
Module: standing
Layer: engines
Purpose: Pure function derive_standing + Standing enum for the relationship affinity engine.
         Converts a (trust, fear, affection) vector into one of five named Standing bands.
Does NOT: perform I/O, call the graph, or invoke LLM services.
Dependencies injected: None (pure function, no external state).
Used by: npc_engine.api.routes.relationship, future gossip/dialogue consumers.
"""

from __future__ import annotations

import enum

# ---------------------------------------------------------------------------
# Composite-score clamp bounds
# ---------------------------------------------------------------------------

CLAMP_MIN: int = -100
CLAMP_MAX: int = 100

# ---------------------------------------------------------------------------
# Band threshold constants (UPPER_SNAKE — no magic numbers in derive_standing)
#
# Bands (half-open on the upper end except NEUTRAL and ALLIED):
#   HOSTILE:  [CLAMP_MIN,  HOSTILE_MAX)  i.e. score < HOSTILE_MAX
#   WARY:     [HOSTILE_MAX, WARY_MAX)    i.e. HOSTILE_MAX <= score < WARY_MAX
#   NEUTRAL:  [WARY_MAX,   NEUTRAL_MAX]  i.e. WARY_MAX <= score <= NEUTRAL_MAX
#   FRIENDLY: (NEUTRAL_MAX, ALLIED_MIN]  i.e. NEUTRAL_MAX < score <= ALLIED_MIN
#   ALLIED:   (ALLIED_MIN,  CLAMP_MAX]   i.e. score > ALLIED_MIN
# ---------------------------------------------------------------------------

HOSTILE_MAX: int = -50   # lower bound of WARY; scores strictly below this are HOSTILE
WARY_MAX: int = -15      # lower bound of NEUTRAL; scores strictly below this (but >= HOSTILE_MAX) are WARY
NEUTRAL_MAX: int = 15    # upper bound of NEUTRAL (inclusive)
ALLIED_MIN: int = 50     # upper bound of FRIENDLY (inclusive); scores strictly above this are ALLIED

# Aliases exported for test assertions (NEUTRAL_MIN == WARY_MAX, FRIENDLY_MIN == NEUTRAL_MAX)
NEUTRAL_MIN: int = WARY_MAX
FRIENDLY_MIN: int = NEUTRAL_MAX


class Standing(str, enum.Enum):
    """Named relationship standing band derived from the affinity composite score.

    Bands (composite = clamp(trust + affection - fear, -100, 100)):
        HOSTILE:  [-100, -50)
        WARY:     [-50,  -15)
        NEUTRAL:  [-15,   15]
        FRIENDLY: ( 15,   50]
        ALLIED:   ( 50,  100]
    """

    HOSTILE = "HOSTILE"
    WARY = "WARY"
    NEUTRAL = "NEUTRAL"
    FRIENDLY = "FRIENDLY"
    ALLIED = "ALLIED"


def derive_standing(*, trust: int, fear: int, affection: int) -> Standing:
    """Derive a Standing band from raw relation scalars.

    Composite score: clamp(trust + affection - fear, -100, 100).
    Band boundaries use module-level UPPER_SNAKE constants — no magic numbers here.

    Args:
        trust: Raw trust scalar (any integer; clamping applied internally).
        fear: Raw fear scalar (any integer; clamping applied internally).
        affection: Raw affection scalar (any integer; clamping applied internally).

    Returns:
        The Standing band corresponding to the clamped composite score.
    """
    raw = trust + affection - fear
    score = max(CLAMP_MIN, min(CLAMP_MAX, raw))

    if score < HOSTILE_MAX:
        return Standing.HOSTILE
    if score < WARY_MAX:
        return Standing.WARY
    if score <= NEUTRAL_MAX:
        return Standing.NEUTRAL
    if score <= ALLIED_MIN:
        return Standing.FRIENDLY
    return Standing.ALLIED
