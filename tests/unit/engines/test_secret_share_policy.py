"""
test_secret_share_policy.py - Unit tests for the standing-gated secret-share policy (F3.1).

Verifies that secret-share probability is monotonic non-decreasing across rising
Standing bands and that low/hostile bands never share.

Dependencies injected: none (pure function).
"""

from __future__ import annotations

from npc_engine.engines.gossip.secret_share_policy import secret_share_probability
from npc_engine.engines.relationship.standing import Standing


def test_hostile_and_wary_never_share() -> None:
    """HOSTILE and WARY standings gate secrets off entirely (probability 0)."""
    assert secret_share_probability(Standing.HOSTILE) == 0.0
    assert secret_share_probability(Standing.WARY) == 0.0


def test_probability_increases_with_standing() -> None:
    """Secret-share probability is monotonic non-decreasing from NEUTRAL up."""
    order = [Standing.NEUTRAL, Standing.FRIENDLY, Standing.ALLIED]
    probs = [secret_share_probability(s) for s in order]
    assert probs == sorted(probs)
    assert probs[0] > 0.0  # NEUTRAL allows some sharing
    assert probs[-1] <= 1.0


def test_allied_shares_most() -> None:
    """ALLIED is the strongest sharer band."""
    allied = secret_share_probability(Standing.ALLIED)
    assert allied == max(secret_share_probability(s) for s in Standing)
