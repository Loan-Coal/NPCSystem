"""
Module: sequence_order_effect
Layer: evals (eval harness — not part of src/)
Purpose: The order-effect check (docs/SEQUENCE_STATS_POLICY.md §4) — Cochran's Q
         across repetition indices and first-vs-last McNemar — computed pooled
         across the promoted scenario battery. It is the primary statistic a
         PARTIAL-fidelity run reports in place of the withheld Wilson interval.
Dependencies: math (stdlib), pydantic, chi_square (evals/), paired_stats (evals/)
Used by: evals/sequence_rates.py (EVAL-P12.4)

DESIGN NOTE (documented in DECISIONS.md at EVAL-P12.4): SEQUENCE_STATS_POLICY §4.2's
formula is stated over a per-turn block design — Lᵢ = passes at repetition i summed
across *evaluated turns*, Cⱼ = passes for turn j summed across repetitions. The v1
sequence_runner (evals/sequence_runner.py) records one pass/fail boolean per
repetition per *scenario*, not per turn — that finer-grained Turn-level record is
the v2 schema (sequence_records.py), reserved for the future EVAL-P14 runner. This
module substitutes "scenario" for "turn" as the block-design column: with 6 promoted
scenarios sharing one k, the matrix is [scenario][repetition], which is exactly the
shape available today and is non-degenerate (a single-column matrix would make Q
trivially equal to k-1 for any run with mixed outcomes — see the DECISIONS entry for
the derivation). Cochran's Q and McNemar are computed once, over the pooled battery,
not once per scenario.
"""

from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, ConfigDict

from chi_square import chi2_sf
from paired_stats import mcnemar_exact

_MIN_K_FOR_COCHRANS_Q: int = 3


class OrderEffectResult(BaseModel):
    """Result of the order-effect check pooled across the promoted scenario battery.

    Attributes:
        computable: Whether Cochran's Q could be computed at all.
        reason: Why it could not be computed, when `computable` is False.
        cochrans_q: The Q statistic, or None when not computable.
        cochrans_q_p: Cochran's Q p-value (chi-square(k-1) upper tail), or None.
        mcnemar_p: First-vs-last McNemar two-sided exact p-value, or None when
            the two ends have no discordant pairs (test undefined).
        rates_by_repetition: Pass rate at each repetition index, pooled across
            all scenarios in the battery — direction/monotonicity is visible here
            even when neither test is computable.
    """

    model_config = ConfigDict(frozen=True)

    computable: bool
    reason: str | None
    cochrans_q: float | None
    cochrans_q_p: float | None
    mcnemar_p: float | None
    rates_by_repetition: tuple[float, ...]


def _rates_by_repetition(outcomes: Sequence[Sequence[bool]], k: int) -> tuple[float, ...]:
    """Pass rate at each repetition index, pooled across all scenario rows."""
    n_scenarios = len(outcomes)
    return tuple(
        sum(1 for row in outcomes if row[i]) / n_scenarios for i in range(k)
    )


def _cochrans_q(outcomes: Sequence[Sequence[bool]], k: int) -> tuple[float, float] | None:
    """Compute Cochran's Q and its p-value, or None if the denominator is degenerate."""
    row_sums = tuple(sum(1 for cell in row if cell) for row in outcomes)  # C_j per scenario
    col_sums = tuple(
        sum(1 for row in outcomes if row[i]) for i in range(k)
    )  # L_i per repetition index

    denominator = sum(c * (k - c) for c in row_sums)
    if denominator == 0:
        return None  # every scenario is uniformly all-pass or all-fail: Q is undefined

    numerator = (k - 1) * (k * sum(col * col for col in col_sums) - sum(col_sums) ** 2)
    q = numerator / denominator
    p = chi2_sf(q, df=k - 1)
    return (q, p)


def _mcnemar_first_vs_last(outcomes: Sequence[Sequence[bool]]) -> float | None:
    """First-vs-last McNemar p-value, pairing rep[0] against rep[-1] per scenario row."""
    regressed = sum(1 for row in outcomes if row[0] and not row[-1])  # b: passed then failed
    improved = sum(1 for row in outcomes if not row[0] and row[-1])  # c: failed then passed
    if regressed == 0 and improved == 0:
        return None
    return float(mcnemar_exact(regressed, improved))


def order_effect_check(outcomes: Sequence[Sequence[bool]]) -> OrderEffectResult:
    """Run the order-effect check over a pooled scenario-by-repetition outcome matrix.

    Args:
        outcomes: One row per scenario, one boolean column per repetition index.
            Every row must have the same length k (all scenarios share one run's k).
    Returns:
        OrderEffectResult. `computable` is False (with `reason` set) when Cochran's
        Q cannot be computed — k < 3, or every scenario is uniformly pass/fail.
    Raises:
        ValueError: When outcomes is empty, or rows have inconsistent lengths.
    """
    if not outcomes:
        raise ValueError("order_effect_check requires at least one scenario row")
    k = len(outcomes[0])
    if any(len(row) != k for row in outcomes):
        raise ValueError("order_effect_check requires every scenario row to share the same k")

    mcnemar_p = _mcnemar_first_vs_last(outcomes)

    if k < _MIN_K_FOR_COCHRANS_Q:
        return OrderEffectResult(
            computable=False,
            reason=f"k={k} < {_MIN_K_FOR_COCHRANS_Q}: Cochran's Q requires k >= 3",
            cochrans_q=None,
            cochrans_q_p=None,
            mcnemar_p=mcnemar_p,
            rates_by_repetition=_rates_by_repetition(outcomes, k),
        )

    q_result = _cochrans_q(outcomes, k)
    if q_result is None:
        return OrderEffectResult(
            computable=False,
            reason="every scenario produced a uniform outcome across repetitions",
            cochrans_q=None,
            cochrans_q_p=None,
            mcnemar_p=mcnemar_p,
            rates_by_repetition=_rates_by_repetition(outcomes, k),
        )

    q, p = q_result
    return OrderEffectResult(
        computable=True,
        reason=None,
        cochrans_q=q,
        cochrans_q_p=p,
        mcnemar_p=mcnemar_p,
        rates_by_repetition=_rates_by_repetition(outcomes, k),
    )
