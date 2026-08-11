"""
Module: battery_rates
Layer: evals (utility)
Purpose: Rao-Scott design-effect corrected pass rate for batteries of k-repeated
         eval cases. Keeps all n·k observations for the point estimate; corrects
         only the 95% Wilson interval for intra-case correlation via the ANOVA ICC
         estimator. At rho→1 (near-identical repetitions), n_eff→n_cases.
Dependencies: math, rate_stats
Used by: evals/summary.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rate_stats import Z_95

_Z_SQ: float = Z_95 * Z_95
_MIN_N_EFF: float = 1.0


@dataclass(frozen=True)
class BatteryRate:
    """Rao-Scott corrected pass rate for one battery of k-repeated eval cases.

    Attributes:
        n_records: Total records (n_cases × k, the k-inflated denominator).
        n_cases: Number of unique cases.
        k: Average repetitions per case (n_records / n_cases).
        passes: Total passing records.
        pass_rate: Point estimate (passes / n_records).
        rho: ANOVA intra-class correlation, clamped to [0, 1].
        deff: Design effect: 1 + (k − 1) × rho.
        n_eff: Effective sample size: n_records / deff.
        ci_low: Lower bound of the 95% design-effect-corrected Wilson CI.
        ci_high: Upper bound of the 95% design-effect-corrected Wilson CI.
    """

    n_records: int
    n_cases: int
    k: float
    passes: int
    pass_rate: float
    rho: float
    deff: float
    n_eff: float
    ci_low: float
    ci_high: float

    def format_summary(self) -> str:
        """Format as 'passes/records (n_cases=N, k=K, n_eff=E, rho=R)'."""
        return (
            f"{self.passes}/{self.n_records} "
            f"(n_cases={self.n_cases}, k={self.k:.1f}, "
            f"n_eff={self.n_eff:.1f}, rho={self.rho:.3f})"
        )


def _is_skipped(result: dict) -> bool:
    """True when a result dict has no expectations or all are skipped."""
    expectations = result.get("expectations", [])
    if not expectations:
        return True
    return all(exp.get("skipped") for exp in expectations)


def _ss_between_within(
    case_passes: list[int],
    case_ks: list[int],
    grand_mean: float,
) -> tuple[float, float]:
    """Sum of squares between and within groups for Bernoulli outcomes.

    Args:
        case_passes: Pass count per case.
        case_ks: Repetition count per case.
        grand_mean: Grand pass rate (total_passes / total_records).
    Returns:
        (ss_between, ss_within).
    """
    ss_between = sum(
        k_i * (p_i / k_i - grand_mean) ** 2
        for p_i, k_i in zip(case_passes, case_ks)
    )
    ss_within = sum(
        k_i * (p_i / k_i) * (1.0 - p_i / k_i)
        for p_i, k_i in zip(case_passes, case_ks)
    )
    return ss_between, ss_within


def _icc_anova(case_passes: list[int], case_ks: list[int]) -> float:
    """ANOVA intra-class correlation for binary outcomes, clamped to [0, 1].

    Uses the one-way ANOVA estimator applied to Bernoulli outcomes. Returns 0.0
    when df_within == 0 (all cases have k == 1) or when the denominator is ≤ 0.

    Args:
        case_passes: Pass count per case (len == n_cases).
        case_ks: Repetition count per case (same length as case_passes).
    Returns:
        ICC in [0.0, 1.0].
    """
    n_cases = len(case_passes)
    if n_cases <= 1:
        return 0.0
    n_records = sum(case_ks)
    grand_mean = sum(case_passes) / n_records
    ss_between, ss_within = _ss_between_within(case_passes, case_ks, grand_mean)
    df_between = n_cases - 1
    df_within = n_records - n_cases
    if df_within == 0:
        return 0.0
    msb = ss_between / df_between
    msw = ss_within / df_within
    k_bar = n_records / n_cases
    denominator = msb + (k_bar - 1.0) * msw
    if denominator <= 0.0:
        return 0.0
    return max(0.0, min(1.0, (msb - msw) / denominator))


def _wilson_from_p_hat(p_hat: float, n_eff: float) -> tuple[float, float]:
    """Wilson 95% CI using p_hat as the point estimate and n_eff as sample size.

    Equivalent to wilson_interval(p_hat * n_eff, n_eff) for non-integer n_eff.
    Uses float n_eff directly without rounding so the corrected interval is exact.

    Args:
        p_hat: Point estimate in [0, 1].
        n_eff: Effective sample size (> 0).
    Returns:
        (ci_low, ci_high) clipped to [0, 1].
    """
    denom = 1.0 + _Z_SQ / n_eff
    center = (p_hat + _Z_SQ / (2.0 * n_eff)) / denom
    margin = (
        Z_95
        * math.sqrt(p_hat * (1.0 - p_hat) / n_eff + _Z_SQ / (4.0 * n_eff * n_eff))
        / denom
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _group_results_by_case(results: list[dict]) -> dict[str, list[bool]]:
    """Group evaluated result dicts by case_id, returning pass/fail booleans.

    Args:
        results: Per-case result dicts; skipped dicts are excluded.
    Returns:
        Dict mapping case_id → list of bool outcomes (one per evaluated record).
    """
    groups: dict[str, list[bool]] = {}
    for r in results:
        if _is_skipped(r):
            continue
        case_id = r.get("case_id", "")
        groups.setdefault(case_id, []).append(bool(r.get("passed", False)))
    return groups


def _build_battery_rate(groups: dict[str, list[bool]]) -> BatteryRate:
    """Build a BatteryRate from non-empty grouped case outcomes.

    Args:
        groups: case_id → list of bool outcomes; must be non-empty.
    Returns:
        BatteryRate with DEFF-corrected CI.
    """
    case_passes = [sum(v) for v in groups.values()]
    case_ks = [len(v) for v in groups.values()]
    n_cases = len(groups)
    n_records = sum(case_ks)
    total_passes = sum(case_passes)
    p_hat = total_passes / n_records
    k_bar = n_records / n_cases
    rho = _icc_anova(case_passes, case_ks)
    deff = 1.0 + (k_bar - 1.0) * rho
    n_eff = max(_MIN_N_EFF, n_records / deff)
    ci_low, ci_high = _wilson_from_p_hat(p_hat, n_eff)
    return BatteryRate(
        n_records=n_records,
        n_cases=n_cases,
        k=k_bar,
        passes=total_passes,
        pass_rate=p_hat,
        rho=rho,
        deff=deff,
        n_eff=n_eff,
        ci_low=ci_low,
        ci_high=ci_high,
    )


def compute_battery_rate(results: list[dict]) -> BatteryRate | None:
    """Rao-Scott corrected pass rate from a battery of eval result dicts.

    Groups result dicts by case_id, computes the ANOVA ICC, and corrects the
    Wilson CI with n_eff = n_records / DEFF. The point estimate is unchanged.

    Args:
        results: Per-case result dicts (runner._run_case or group_by_case shape).
    Returns:
        BatteryRate with DEFF-corrected CI, or None when no evaluated results.
    """
    groups = _group_results_by_case(results)
    if not groups:
        return None
    return _build_battery_rate(groups)
