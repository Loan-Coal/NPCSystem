"""
Module: tests.unit.evals.test_mde
Layer: test (unit)
Purpose: Pin the minimum-detectable-effect arithmetic P9 computes, including the
         consistency check that reproduces the recorded >=6.4pp floor from n=78.
Dependencies: pytest; evals.mde
Used by: make test (pytest discovery)

The numbers here are not invented. `src/npc_engine/config/llm_config.yaml` records
">=6.4pp drop on guard (n=78)" and "refusal_judge at kappa 0.225 (ISSUE-184)"; ISSUE-184
records tone_judge 1.000, affirms_judge 0.282, and a pass base rate of 0.951 over 345
records. Everything below is derived from those.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from mde import (  # noqa: E402
    RECORDED_GUARD_FLOOR_PP,
    RECORDED_GUARD_N,
    JudgeCriterion,
    arm_pairing_mde,
    implied_discordance_rate,
    observed_mde,
    required_pairs_for,
)


def test_the_recorded_floor_is_reproduced_from_the_recorded_n() -> None:
    """The consistency check that makes every other number here trustworthy.

    The 6.4pp floor and the n=78 were recorded independently of this module. If the
    discordance rate implied by one, fed back through the formula, does not return the
    other, then this module is not modelling the test that produced the recorded floor
    and none of its MDEs mean anything.
    """
    p_d = implied_discordance_rate(
        mde=RECORDED_GUARD_FLOOR_PP / 100.0, n_pairs=RECORDED_GUARD_N
    )
    round_trip = observed_mde(n_pairs=RECORDED_GUARD_N, discordance_rate=p_d)
    assert round_trip == pytest.approx(RECORDED_GUARD_FLOOR_PP / 100.0, abs=1e-9)


def test_the_implied_discordance_rate_is_physically_possible() -> None:
    """A discordance rate outside [0, 1] would mean the recorded floor cannot have come
    from a McNemar-style paired test at that n, which is itself a finding."""
    p_d = implied_discordance_rate(
        mde=RECORDED_GUARD_FLOOR_PP / 100.0, n_pairs=RECORDED_GUARD_N
    )
    assert 0.0 < p_d < 1.0
    # And below the independence upper bound 2*p*(1-p) at the recorded base rate 0.951 —
    # a PAIRED design is expected to be more concordant than two independent samples.
    assert p_d < 2 * 0.951 * (1 - 0.951)


def test_more_pairs_lower_the_detectable_effect() -> None:
    """Monotonicity. Without it the 'what n would we need' answer is meaningless."""
    small = observed_mde(n_pairs=78, discordance_rate=0.04)
    large = observed_mde(n_pairs=780, discordance_rate=0.04)
    assert large < small


def test_a_noisier_judge_needs_a_larger_true_effect() -> None:
    """The whole point of folding kappa in: an effect the judge cannot resolve is not
    detectable however large the sample, and refusal_judge sits at 0.225."""
    clean = arm_pairing_mde(
        criterion=JudgeCriterion(name="tone_judge", kappa=1.0),
        n_pairs=78,
        discordance_rate=0.04,
    )
    noisy = arm_pairing_mde(
        criterion=JudgeCriterion(name="refusal_judge", kappa=0.225),
        n_pairs=78,
        discordance_rate=0.04,
    )
    assert noisy.true_mde_pp > clean.true_mde_pp
    assert clean.true_mde_pp == pytest.approx(clean.observed_mde_pp)


def test_a_perfect_judge_does_not_inflate_the_effect() -> None:
    """kappa 1.0 must be the identity, or the attenuation correction is mis-signed."""
    result = arm_pairing_mde(
        criterion=JudgeCriterion(name="tone_judge", kappa=1.0),
        n_pairs=78,
        discordance_rate=0.04,
    )
    assert result.true_mde_pp == pytest.approx(result.observed_mde_pp)


def test_a_zero_kappa_judge_can_never_resolve_anything() -> None:
    """kappa 0 means the judge agrees with itself at chance. The honest answer is that
    no true effect is detectable, not a division-by-zero traceback in a gate."""
    result = arm_pairing_mde(
        criterion=JudgeCriterion(name="broken", kappa=0.0),
        n_pairs=78,
        discordance_rate=0.04,
    )
    assert result.true_mde_pp == float("inf")
    assert result.detectable is False


def test_a_true_effect_above_one_hundred_points_is_not_detectable() -> None:
    """An MDE of 130pp is arithmetic, not a plan: a rate cannot move more than 100
    points, so the gate must report the arm as unresolvable rather than merely large."""
    result = arm_pairing_mde(
        criterion=JudgeCriterion(name="refusal_judge", kappa=0.05),
        n_pairs=78,
        discordance_rate=0.04,
    )
    assert result.true_mde_pp > 100.0
    assert result.detectable is False


def test_correcting_for_multiplicity_raises_the_floor() -> None:
    """P9 split wide_rag into two arms. Three pairings against default rather than two
    is P9's OWN doing, and under any multiplicity control it raises the bar."""
    two = arm_pairing_mde(
        criterion=JudgeCriterion(name="tone_judge", kappa=1.0),
        n_pairs=78,
        discordance_rate=0.04,
        comparisons=2,
    )
    three = arm_pairing_mde(
        criterion=JudgeCriterion(name="tone_judge", kappa=1.0),
        n_pairs=78,
        discordance_rate=0.04,
        comparisons=3,
    )
    assert three.observed_mde_pp > two.observed_mde_pp


def test_required_pairs_scales_as_the_inverse_square_of_the_effect() -> None:
    """Halving the effect you want to see must quadruple the pairs. This is the number
    that turns 'not detectable' into 'not detectable at any n you would pay for'."""
    big = required_pairs_for(true_effect_pp=12.8, kappa=0.225, discordance_rate=0.04)
    small = required_pairs_for(true_effect_pp=6.4, kappa=0.225, discordance_rate=0.04)
    assert small == pytest.approx(4 * big, rel=0.01)


def test_required_pairs_is_infinite_for_a_chance_level_judge() -> None:
    """No sample size rescues a judge at kappa 0; saying so is the useful answer."""
    assert required_pairs_for(
        true_effect_pp=6.4, kappa=0.0, discordance_rate=0.04
    ) == float("inf")
