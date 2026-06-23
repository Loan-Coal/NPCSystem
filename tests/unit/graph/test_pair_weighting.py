"""
test_pair_weighting.py - Unit tests for compute_faction_weight pure function.

Does NOT: access databases or external services.

Dependencies injected: None.
"""

import pytest

from npc_engine.engines.gossip.pair_weighting import compute_faction_weight

BOOST_SAME = 2.0
BOOST_ALLIED = 1.5
PENALTY_HOSTILE = 0.1


def _weight(
    a_factions: set[str],
    b_factions: set[str],
    standing: int | None,
) -> float:
    return compute_faction_weight(
        sharer_faction_ids=a_factions,
        receiver_faction_ids=b_factions,
        best_standing=standing,
        same_faction_boost=BOOST_SAME,
        allied_boost=BOOST_ALLIED,
        hostile_penalty=PENALTY_HOSTILE,
    )


def test_shared_faction_returns_same_faction_boost() -> None:
    result = _weight({"guild_a", "guild_b"}, {"guild_b", "guild_c"}, standing=None)
    assert result == BOOST_SAME


def test_allied_standing_returns_allied_boost() -> None:
    result = _weight({"guild_a"}, {"guild_b"}, standing=50)
    assert result == BOOST_ALLIED


def test_standing_exactly_allied_threshold_returns_allied_boost() -> None:
    result = _weight(set(), {"guild_b"}, standing=50)
    assert result == BOOST_ALLIED


def test_hostile_standing_returns_hostile_penalty() -> None:
    result = _weight({"guild_a"}, {"guild_b"}, standing=-50)
    assert result == PENALTY_HOSTILE


def test_standing_exactly_hostile_threshold_returns_penalty() -> None:
    result = _weight(set(), set(), standing=-50)
    assert result == PENALTY_HOSTILE


def test_neutral_standing_returns_one() -> None:
    result = _weight({"guild_a"}, {"guild_b"}, standing=0)
    assert result == 1.0


def test_no_factions_no_standing_returns_one() -> None:
    result = _weight(set(), set(), standing=None)
    assert result == 1.0


def test_shared_faction_takes_precedence_over_hostile_standing() -> None:
    result = _weight({"guild_a"}, {"guild_a"}, standing=-100)
    assert result == BOOST_SAME


def test_shared_faction_takes_precedence_over_allied_standing() -> None:
    result = _weight({"guild_a"}, {"guild_a"}, standing=100)
    assert result == BOOST_SAME


def test_standing_between_thresholds_returns_one() -> None:
    for standing in (-49, -1, 1, 49):
        result = _weight({"guild_a"}, {"guild_b"}, standing=standing)
        assert result == 1.0, f"expected 1.0 for standing={standing}, got {result}"


def test_no_factions_allied_standing_returns_allied_boost() -> None:
    result = _weight(set(), set(), standing=75)
    assert result == BOOST_ALLIED


def test_no_factions_hostile_standing_returns_hostile_penalty() -> None:
    result = _weight(set(), set(), standing=-75)
    assert result == PENALTY_HOSTILE
