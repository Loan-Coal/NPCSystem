"""
test_gossip_distort.py - Unit tests for deterministic gossip distortion behavior.

Does NOT: execute graph I/O.

Dependencies injected: None.
"""

from npc_engine.engines.gossip.gossip_distort import GossipDistortion, gossip_distort

# Inputs from former eval case faction_gossip_distortion_001 (ISSUE-042)
_HOSTILE_SUMMARY = "The northern army captured the bridge at dawn."
_HOSTILE_KWARGS = dict(
    event_summary=_HOSTILE_SUMMARY,
    sharer_honesty=50,
    sharer_receiver_trust=30,
    event_severity=70,
    tick_id=42,
    distortion_base=0.3,
    faction_standing=-100,
    hostile_distortion_factor=1.5,
)


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


def test_hostile_faction_gossip_produces_distortion() -> None:
    """Hostile faction pair (standing=-100, factor=1.5) guarantees distortion."""
    result: GossipDistortion = gossip_distort(**_HOSTILE_KWARGS)
    assert result.distortion_type is not None, "hostile pair must produce a distortion_type"
    assert 1 <= result.distortion_level <= 100
    assert result.distortion_type in {"omission", "exaggeration", "role_swap", "timeline_shift"}


def test_hostile_faction_gossip_distortion_level_in_range() -> None:
    result: GossipDistortion = gossip_distort(**_HOSTILE_KWARGS)
    assert 20 <= result.distortion_level <= 100


def test_canonical_event_never_distorted() -> None:
    result = gossip_distort(
        event_summary="Official decree: peace declared.",
        sharer_honesty=10,
        sharer_receiver_trust=0,
        event_severity=100,
        tick_id=1,
        distortion_base=1.0,
        is_canonical=True,
    )
    assert result.distortion_type is None
    assert result.distortion_level == 0
    assert result.summary == "Official decree: peace declared."


# ---------------------------------------------------------------------------
# EXP-213: Confidence-biased distortion routing
# ---------------------------------------------------------------------------

_CONFIDENCE_BASE_KWARGS = dict(
    event_summary="The northern army captured the bridge at dawn.",
    sharer_honesty=10,
    sharer_receiver_trust=10,
    event_severity=90,
    tick_id=7,
    distortion_base=1.0,  # Force distortion for these tests (probability=1.0)
    faction_standing=-100,
    hostile_distortion_factor=1.5,
)


def test_confidence_biases_distortion_deterministically() -> None:
    """Same seed but differing receiver_confidence → different distortion type.

    Low confidence (credulous doubtful receiver) vs high confidence receiver
    must yield different distortion_type values for the same event+seed.
    Both calls must be internally deterministic (calling twice → same result).
    """
    result_low_a = gossip_distort(**_CONFIDENCE_BASE_KWARGS, receiver_confidence=10)
    result_low_b = gossip_distort(**_CONFIDENCE_BASE_KWARGS, receiver_confidence=10)
    result_high_a = gossip_distort(**_CONFIDENCE_BASE_KWARGS, receiver_confidence=90)
    result_high_b = gossip_distort(**_CONFIDENCE_BASE_KWARGS, receiver_confidence=90)

    # Each confidence level is internally deterministic.
    assert result_low_a == result_low_b, "low-confidence result must be deterministic"
    assert result_high_a == result_high_b, "high-confidence result must be deterministic"

    # Different confidence levels must produce different distortion types.
    assert result_low_a.distortion_type != result_high_a.distortion_type, (
        "low vs high confidence must bias to a different distortion type"
    )


def test_absent_confidence_matches_current() -> None:
    """When receiver_confidence is absent (None), result is identical to pre-EXP-213 behavior."""
    without_confidence = gossip_distort(**_CONFIDENCE_BASE_KWARGS)
    with_none_explicit = gossip_distort(**_CONFIDENCE_BASE_KWARGS, receiver_confidence=None)
    assert without_confidence == with_none_explicit, (
        "omitting receiver_confidence must be identical to passing None"
    )
