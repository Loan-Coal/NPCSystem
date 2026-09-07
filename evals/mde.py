"""
Module: mde
Layer: evals (eval harness — not part of src/)
Purpose: The minimum detectable effect for ONE arm pairing, computed from the recorded
         sample size and the recorded per-criterion judge reliability. This is the gate
         that can say a ten-hour paired generation is pointless while cancelling it still
         costs five minutes.
Does NOT: run an eval, read a generation directory, or judge anything.
Dependencies injected: every input is a function argument; nothing is read from disk.
Used by: evals.arm_probe (gate output), P9 close-out.

WHY THIS IS COMPUTED HERE AND NOT IN P10
`src/npc_engine/config/llm_config.yaml` records that a measured effect must be a ">=6.4pp
drop on guard (n=78)" before the regression gate fires, with `refusal_judge` at kappa
0.225 (ISSUE-184). Those two facts bound what ANY arm on this battery can resolve, and
they are knowable before the run rather than after it. Discovering them ten hours into a
generation is the failure this module exists to prevent.

THE MODEL, STATED PLAINLY SO IT CAN BE DISAGREED WITH

1. Paired two-sided test at alpha (default 0.05) and power (default 0.80). For a paired
   binary outcome the detectable risk difference is approximately

       delta = (z_{1-alpha/2} + z_{power}) * sqrt(p_d / n)

   where p_d is the DISCORDANCE rate — the share of pairs where the two arms disagree.
   This is the normal approximation to McNemar's test; it is the standard planning
   formula and it is accurate enough to decide whether to spend ten hours.

2. p_d is not guessed. `implied_discordance_rate` inverts the formula against the
   RECORDED 6.4pp floor at the RECORDED n=78, and the answer (~4.1%) is checked to be
   both physically possible and below the independence bound 2p(1-p) at the recorded
   0.951 base rate — a paired design should be more concordant than two independent
   samples. `test_the_recorded_floor_is_reproduced_from_the_recorded_n` pins the round
   trip, which is what makes every other number here trustworthy rather than plausible.

3. Judge noise attenuates the observed effect. Under nondifferential binary
   misclassification the observed risk difference is the true one multiplied by Youden's
   J = sensitivity + specificity - 1. J is approximated here by the recorded kappa. This
   is an APPROXIMATION and it is the weakest link in the chain: J and kappa coincide only
   when the two raters' marginals match. It is used because kappa is what was actually
   measured, and because the alternative — assuming the judge is perfect — is known to be
   false by a factor of four on refusal_judge. Erring here understates the difficulty,
   never overstates it, since kappa <= J is the usual direction.

4. Multiple arms mean multiple comparisons. P9 split `wide_rag` into two arms, so there
   are now THREE pairings against default where there were two. `comparisons` applies a
   Bonferroni correction to alpha; pass 1 for the uncorrected figure.
"""

from __future__ import annotations

from statistics import NormalDist

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "DEFAULT_ALPHA",
    "DEFAULT_POWER",
    "KAPPA_GENERATION",
    "RECORDED_BASE_RATE",
    "RECORDED_GUARD_FLOOR_PP",
    "RECORDED_GUARD_N",
    "RECORDED_KAPPAS",
    "ArmPairingMde",
    "JudgeCriterion",
    "arm_pairing_mde",
    "implied_discordance_rate",
    "observed_mde",
    "required_pairs_for",
]

DEFAULT_ALPHA: float = 0.05
"""Two-sided significance level."""

DEFAULT_POWER: float = 0.80
"""Conventional target power."""

RECORDED_GUARD_FLOOR_PP: float = 6.4
"""The drop the guard regression gate needs before it fires, in percentage points.

Recorded in src/npc_engine/config/llm_config.yaml, not derived here.
"""

RECORDED_GUARD_N: int = 78
"""Guard PAIRS available to an arm comparison: 78 cases, not 234 turns (ISSUE-254).

The unit is a case, deliberately. The corpus holds 234 guard turns over 78 guard cases at
k=3, and 78 was also — coincidentally — what the broken verdict-source join reported as
`guard_turns` before it was fixed, so this number looks like the stale one. It is not.

Three repetitions of one case are not three independent observations: they share a prompt,
an NPC and a seed, which is exactly the intra-case correlation `battery_rates` measures as
`rho` and discounts via `n_eff`. Pairing per repetition and passing the raw 234 would
overstate power by about sqrt(3) and make the judges look more discriminating than they
are — the failure this phase exists to remove.

Note that raising n alone would not move `observed_mde`: `implied_discordance_rate` derives
p_d from the recorded floor AT the recorded n, so re-applying it returns the floor either
way. What the unit changes is `required_pairs_for`, and what "a pair" means to anyone
reading the output.

If the arm design is ever changed to pair per repetition, take `n_eff` from
`battery_rates.compute_battery_rate` rather than the raw turn count. Pinned by
tests/unit/evals/test_guard_pairing_unit.py.
"""

KAPPA_GENERATION: str = "k3_73e6c36"
"""The generation both RECORDED_KAPPAS and RECORDED_BASE_RATE are measured on.

Named rather than implied so the pair cannot drift apart, and so a reader can re-derive
either number from one place. All 393 calibration labels carry this gen_id.
"""

RECORDED_BASE_RATE: float = 0.9536
"""Pass base rate over the 345 LLM-judged records of KAPPA_GENERATION.

Its role here is a sanity bound: it caps how concordant two arms can plausibly be,
via the independence bound 2p(1-p).

ISSUE-253: this read 0.951 until 2026-09-01. That was not invented — it is exactly
328/345, the rate in `judged.jsonl.pre-panel-20260817_192458.bak`. The panel re-judge of
2026-08-18 flipped one record to 329/345 = 0.9536 and the constant was never updated, so
a correct number went stale by a single verdict. The independence bound it feeds moves
from 9.32% to 8.83% as a result — small, but it is the only check on a discordance rate
that is derived rather than measured.

Bound to its corpus by tests/unit/evals/test_base_rate_matches_its_corpus.py, so the same
drift now fails `make check` instead of surviving three weeks unnoticed.
"""

RECORDED_KAPPAS: tuple[tuple[str, float], ...] = (
    ("tone_judge", 0.849),
    ("affirms_judge", 0.530),
    ("refusal_judge", 0.247),
)
"""Per-criterion kappa from CALIBRATION against human labels — the authoritative family.

refusal_judge is retired (measurement-remediation Phase 2c, DEC-269 — folded into
affirms_judge). Kept here as a historical measurement, not a live scorer: its 75
labels stay in evals/calibration/labels_v1.jsonl and its 0.247 kappa is real, but
no future generation will produce new refusal_judge rows to recompute it against.

ISSUE-244: three rival kappa families circulated for the same scorers.
  * calibration vs human labels: 0.849 / 0.530 / 0.247  <- these, and the reason below
  * inter-panel Fleiss (judge vs judge): 1.000 / 0.282 / 0.225  <- what this held before
  * per-criterion panel Fleiss: 0.753 / 0.519 / 0.422

Calibration wins because of what kappa is used for here. `arm_pairing_mde` computes
`true_mde = observed_mde / kappa` — it undoes judge noise to ask what underlying effect
must exist. The relevant noise is the judge's disagreement with GROUND TRUTH, which is
what calibration measures. Inter-panel agreement measures whether three judges share a
bias, and three judges can agree perfectly while all being wrong: tone_judge was
unanimous 135/135, which is exactly how it came to read 1.000. A kappa of 1.000 makes
the division a no-op and silently asserts the judge adds no noise at all.

Provenance: measured on generation `k3_73e6c36` (all 393 calibration labels carry that
gen_id), not on the current `k3_77688e7_regen1`. That is intended — calibration describes
the judge, not the generation — but it means these numbers do not move when a new
generation lands, and they go stale when the judge prompts change. Recorded in
`evals/trend/trend_v1.jsonl`'s `scorer_kappas`, pinned by
`tests/unit/evals/test_kappas_match_calibration.py`. See DEC-240.
"""

_MAX_POSSIBLE_EFFECT_PP: float = 100.0
"""A rate cannot move more than 100 points, so a larger MDE is not a plan."""


class JudgeCriterion(BaseModel):
    """One judge criterion and the chance-corrected agreement measured for it.

    Attributes:
        name: Criterion name as it appears in the judge prompts and panel metrics.
        kappa: Fleiss kappa over the calibration records. 0.0 means chance-level.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    kappa: float = Field(ge=0.0, le=1.0)


class ArmPairingMde(BaseModel):
    """What one (default vs arm) comparison can resolve on one criterion.

    Attributes:
        criterion: The judge criterion this row describes.
        n_pairs: Paired records available for the comparison.
        discordance_rate: Share of pairs on which the two arms are expected to disagree.
        comparisons: Number of simultaneous pairings the alpha was corrected for.
        observed_mde_pp: Smallest difference in JUDGED pass rate the test could call
            significant, in percentage points.
        true_mde_pp: The underlying effect that would have to exist to produce that
            observed difference, once judge noise is undone. Infinite at kappa 0.
        detectable: Whether true_mde_pp is a possible movement at all — a rate cannot
            move more than 100 points.
    """

    model_config = ConfigDict(frozen=True)

    criterion: JudgeCriterion
    n_pairs: int
    discordance_rate: float
    comparisons: int
    observed_mde_pp: float
    true_mde_pp: float
    detectable: bool


def _z_sum(alpha: float, power: float, comparisons: int) -> float:
    """Return z_{1-alpha/2} + z_{power}, with alpha Bonferroni-corrected."""
    corrected = alpha / max(1, comparisons)
    normal = NormalDist()
    return normal.inv_cdf(1.0 - corrected / 2.0) + normal.inv_cdf(power)


def observed_mde(
    *,
    n_pairs: int,
    discordance_rate: float,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
    comparisons: int = 1,
) -> float:
    """Smallest JUDGED rate difference a paired test could call significant.

    Args:
        n_pairs: Paired records available.
        discordance_rate: Share of pairs where the arms disagree.
        alpha: Two-sided significance level, before correction.
        power: Target power.
        comparisons: Simultaneous pairings to Bonferroni-correct alpha for.
    Returns:
        The effect as a PROPORTION (0.064 for 6.4pp).
    """
    return float(_z_sum(alpha, power, comparisons) * (discordance_rate / n_pairs) ** 0.5)


def implied_discordance_rate(
    *,
    mde: float,
    n_pairs: int,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
    comparisons: int = 1,
) -> float:
    """Invert `observed_mde` for p_d — what discordance the recorded floor implies.

    This is how the model is calibrated against measurements it did not produce, rather
    than against a guessed discordance rate.

    Args:
        mde: The recorded detectable effect, as a proportion.
        n_pairs: The n that effect was recorded at.
        alpha: Two-sided significance level, before correction.
        power: Target power.
        comparisons: Simultaneous pairings alpha was corrected for.
    Returns:
        The implied discordance rate, as a proportion.
    """
    return float(n_pairs) * (mde / _z_sum(alpha, power, comparisons)) ** 2


def arm_pairing_mde(
    *,
    criterion: JudgeCriterion,
    n_pairs: int,
    discordance_rate: float,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
    comparisons: int = 1,
) -> ArmPairingMde:
    """Resolve one (default vs arm) x (criterion) cell.

    Args:
        criterion: The judge criterion and its measured kappa.
        n_pairs: Paired records available for the comparison.
        discordance_rate: Share of pairs where the arms disagree.
        alpha: Two-sided significance level, before correction.
        power: Target power.
        comparisons: Simultaneous pairings to Bonferroni-correct alpha for.
    Returns:
        The populated ArmPairingMde row.
    """
    observed = observed_mde(
        n_pairs=n_pairs,
        discordance_rate=discordance_rate,
        alpha=alpha,
        power=power,
        comparisons=comparisons,
    )
    observed_pp = observed * 100.0
    true_pp = float("inf") if criterion.kappa <= 0.0 else observed_pp / criterion.kappa
    return ArmPairingMde(
        criterion=criterion,
        n_pairs=n_pairs,
        discordance_rate=discordance_rate,
        comparisons=comparisons,
        observed_mde_pp=observed_pp,
        true_mde_pp=true_pp,
        detectable=true_pp <= _MAX_POSSIBLE_EFFECT_PP,
    )


def required_pairs_for(
    *,
    true_effect_pp: float,
    kappa: float,
    discordance_rate: float,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
    comparisons: int = 1,
) -> float:
    """Pairs needed to detect a given TRUE effect through a judge of this reliability.

    This is what turns "not detectable" into "not detectable at any n you would pay
    for": it scales as the inverse square of the effect and of kappa together.

    Args:
        true_effect_pp: The underlying effect to detect, in percentage points.
        kappa: The judge's chance-corrected agreement.
        discordance_rate: Share of pairs where the arms disagree.
        alpha: Two-sided significance level, before correction.
        power: Target power.
        comparisons: Simultaneous pairings to Bonferroni-correct alpha for.
    Returns:
        Required paired records; infinite when kappa is 0 or the effect is 0.
    """
    observed = (true_effect_pp / 100.0) * kappa
    if observed <= 0.0:
        return float("inf")
    return float(discordance_rate) * (_z_sum(alpha, power, comparisons) / observed) ** 2
