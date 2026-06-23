"""
Tests for the relationship standing derivation engine.
Covers derive_standing across all 5 bands and exact boundary values.
"""

from __future__ import annotations

import pytest

from npc_engine.engines.relationship.standing import (
    ALLIED_MIN,
    FRIENDLY_MIN,
    HOSTILE_MAX,
    NEUTRAL_MAX,
    NEUTRAL_MIN,
    Standing,
    derive_standing,
)


@pytest.mark.parametrize(
    "trust,fear,affection,expected",
    [
        # Representative band values (from spec)
        (60, 0, 0, Standing.ALLIED),      # score = 60 → ALLIED
        (0, 20, 0, Standing.WARY),         # score = -20 → WARY
        (0, 0, 0, Standing.NEUTRAL),       # score = 0 → NEUTRAL
        (30, 0, 0, Standing.FRIENDLY),     # score = 30 → FRIENDLY
        (-100, 100, 0, Standing.HOSTILE),  # raw = -200, clamped to -100 → HOSTILE
        # Exact boundary values
        # standing = -51 → HOSTILE  (inside [-100, -50))
        (0, 51, 0, Standing.HOSTILE),
        # standing = -50 → WARY  (lower inclusive bound of [-50, -15))
        (0, 50, 0, Standing.WARY),
        # standing = -49 → WARY
        (0, 49, 0, Standing.WARY),
        # standing = -16 → WARY  (still in [-50, -15))
        (0, 16, 0, Standing.WARY),
        # standing = -15 → NEUTRAL  (lower inclusive bound of [-15, 15])
        (0, 15, 0, Standing.NEUTRAL),
        # standing = 15 → NEUTRAL  (upper inclusive bound of [-15, 15])
        (15, 0, 0, Standing.NEUTRAL),
        # standing = 16 → FRIENDLY  (first value above NEUTRAL)
        (16, 0, 0, Standing.FRIENDLY),
        # standing = 50 → FRIENDLY  (upper inclusive bound of (15, 50])
        (50, 0, 0, Standing.FRIENDLY),
        # standing = 51 → ALLIED  (first value above FRIENDLY)
        (51, 0, 0, Standing.ALLIED),
        # affection contributes positively
        (0, 0, 20, Standing.FRIENDLY),    # score = 20 → FRIENDLY
        # mixed: trust + affection - fear
        (40, 10, 5, Standing.FRIENDLY),   # 40 + 5 - 10 = 35 → FRIENDLY
    ],
)
def test_derive_standing(trust: int, fear: int, affection: int, expected: Standing) -> None:
    """derive_standing returns the correct Standing band for the given scalars."""
    result = derive_standing(trust=trust, fear=fear, affection=affection)
    assert result == expected, (
        f"derive_standing(trust={trust}, fear={fear}, affection={affection}) "
        f"→ {result!r}, expected {expected!r}"
    )


def test_derive_standing_clamp_upper() -> None:
    """Extreme positive values are clamped to ALLIED."""
    assert derive_standing(trust=100, fear=0, affection=100) == Standing.ALLIED


def test_derive_standing_clamp_lower() -> None:
    """Extreme negative values are clamped to HOSTILE."""
    assert derive_standing(trust=0, fear=100, affection=0) == Standing.HOSTILE


def test_band_constants_no_magic_numbers() -> None:
    """Band cutoffs must be exposed as named module constants (not magic numbers)."""
    # Verify the constants exist and have the expected values from the spec.
    assert HOSTILE_MAX == -50
    assert NEUTRAL_MIN == -15
    assert NEUTRAL_MAX == 15
    assert FRIENDLY_MIN == 15
    assert ALLIED_MIN == 50
