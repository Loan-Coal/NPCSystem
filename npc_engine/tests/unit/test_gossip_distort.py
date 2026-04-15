"""
test_gossip_distort.py - Unit tests for deterministic gossip distortion behavior.

Does NOT: execute graph I/O.

Dependencies injected: None.
"""

from engines.gossip.gossip_distort import gossip_distort


def test_gossip_distort_is_deterministic() -> None:
    first = gossip_distort(
        event_summary="A fire damaged the market.",
        sharer_honesty=35,
        sharer_receiver_trust=40,
        event_severity=70,
        tick_id=12,
        distortion_base=0.3,
    )
    second = gossip_distort(
        event_summary="A fire damaged the market.",
        sharer_honesty=35,
        sharer_receiver_trust=40,
        event_severity=70,
        tick_id=12,
        distortion_base=0.3,
    )
    assert first == second
