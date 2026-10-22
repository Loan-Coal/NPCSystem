"""
Module: test_gossip_distort_compound
Layer: tests/unit/engines/gossip
Purpose: Verifies that gossip distortion compounds across hops — a hop-2 receiver
         accumulates distortion from the hop-1 sharer's prior distortion_level.
         ISSUE-228: level was recomputed from probability alone, ignoring the sharer's
         existing k.distortion_level, so distortion_level never grew across hops.
Does NOT: access databases or external services.
Dependencies: pytest, gossip_distort
"""
from __future__ import annotations

from npc_engine.engines.gossip.gossip_distort import GossipDistortion, gossip_distort

# Parameters verified to trigger distortion at tick_id=2:
# honesty=50, trust=50, severity=60, base=0.3 → probability≈0.63,
# gate at tick=2 is 0.550 < 0.63 → distortion occurs, level=63.
_COMPOUND_KWARGS: dict = dict(
    event_summary="The northern armies have crossed the border.",
    sharer_honesty=50,
    sharer_receiver_trust=50,
    event_severity=60,
    tick_id=2,
    distortion_base=0.3,
)


def test_hop2_distortion_level_exceeds_hop1() -> None:
    """After two gossip hops the distortion_level must compound above the first-hop value.

    Hop-1 sharer starts with prior_distortion_level=0 (first-hand knowledge).
    Hop-2 receiver's level is computed with prior_distortion_level=hop1.distortion_level
    and must strictly exceed it (ISSUE-228).
    """
    hop1: GossipDistortion = gossip_distort(**_COMPOUND_KWARGS, prior_distortion_level=0)
    assert hop1.distortion_level > 0, (
        "precondition: hop-1 must produce distortion at tick=2 with these params"
    )

    hop2: GossipDistortion = gossip_distort(
        **_COMPOUND_KWARGS, prior_distortion_level=hop1.distortion_level
    )
    assert hop2.distortion_level > hop1.distortion_level, (
        f"hop-2 level ({hop2.distortion_level}) must exceed hop-1 level "
        f"({hop1.distortion_level}) — distortion must compound across hops (ISSUE-228)."
    )


def test_zero_prior_level_does_not_change_behavior() -> None:
    """With prior_distortion_level=0 the result is identical to a call without it.

    Backward compatibility: callers that omit prior_distortion_level (first-hand
    witnesses, canonical events) get the same result as before ISSUE-228 fix.
    """
    result_default = gossip_distort(**_COMPOUND_KWARGS)
    result_explicit_zero = gossip_distort(**_COMPOUND_KWARGS, prior_distortion_level=0)
    assert result_default == result_explicit_zero, (
        "prior_distortion_level=0 must produce the same result as omitting the parameter."
    )


def test_distortion_level_capped_at_100() -> None:
    """Compounding must not exceed 100 even with a very high prior level."""
    result = gossip_distort(**_COMPOUND_KWARGS, prior_distortion_level=99)
    assert result.distortion_level <= 100, (
        f"distortion_level {result.distortion_level} exceeds maximum of 100."
    )
