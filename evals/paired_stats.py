"""
Module: paired_stats
Layer: evals (utility)
Purpose: Paired case-level McNemar significance test for comparing two eval runs.
         mcnemar_exact computes the exact binomial two-sided p-value; paired_compare
         reduces two CaseStat tuples to a PairedResult verdict.
Dependencies: math (stdlib), pydantic, case_stats (evals/)
Used by: compare (evals/compare.py — EVAL-P8.2)
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict

from case_stats import CaseStat

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SIGNIFICANCE_THRESHOLD: float = 0.05
_BOUNDARY_CI_EPSILON: float = 1e-9

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class PairedResult(BaseModel):
    """Outcome of a paired case-level McNemar comparison between two eval runs.

    Frozen to ensure immutability after construction.

    Attributes:
        improved: Cases that failed before and passed after (discordant, c).
        regressed: Cases that passed before and failed after (discordant, b).
        unchanged: Cases with the same binary outcome in both runs.
        p_value: Two-sided McNemar exact p-value (1.0 when all pairs concordant).
        verdict: Significance-based direction of change.
    """

    model_config = ConfigDict(frozen=True)

    improved: int
    regressed: int
    unchanged: int
    p_value: float
    verdict: Literal["better", "worse", "no_detectable_change", "regression_evasion"]


# ---------------------------------------------------------------------------
# Boundary CI utilities
# ---------------------------------------------------------------------------


def is_boundary_ci(lo: float, hi: float) -> bool:
    """Return True when a bootstrap CI is degenerate at a boundary.

    A percentile bootstrap returns [v, v] when every resample reaches the same
    value. This signals the estimator is at a natural boundary (e.g. κ=1.0 when
    all samples agree) and the interval conveys zero uncertainty rather than the
    true sampling variance.

    Args:
        lo: Lower bound of the CI.
        hi: Upper bound of the CI.
    Returns:
        True if lo and hi are within _BOUNDARY_CI_EPSILON of each other.
    """
    return abs(hi - lo) < _BOUNDARY_CI_EPSILON


def boundary_ci_note(n_clusters: int) -> str:
    """Format the standard note for a degenerate bootstrap CI at its boundary.

    Args:
        n_clusters: Number of case clusters in the resampling pool.
    Returns:
        Display string suitable for calibration reports.
    """
    return f"interval undefined at boundary (n_clusters={n_clusters})"


# ---------------------------------------------------------------------------
# mcnemar_exact
# ---------------------------------------------------------------------------


def mcnemar_exact(b: int, c: int) -> float:
    """Compute the exact two-sided McNemar p-value from discordant pair counts.

    Uses the exact binomial distribution rather than the χ² approximation.
    The χ² approximation is unreliable when discordant counts are small (< 25).

    Under H₀ (no systematic difference), the smaller of b and c follows
    Binomial(b+c, 0.5) in the lower tail. The two-sided p-value doubles that
    probability and is capped at 1.0.

    Args:
        b: Pairs that passed before and failed after (regressions).
        c: Pairs that failed before and passed after (improvements).
    Returns:
        Two-sided p-value in (0, 1].
    Raises:
        ValueError: When b and c are both 0 — no discordant pairs; test undefined.
    """
    n = b + c
    if n == 0:
        raise ValueError(
            "mcnemar_exact requires at least one discordant pair; "
            "b=0 and c=0 leaves the test undefined."
        )
    tail_sum = sum(math.comb(n, k) for k in range(min(b, c) + 1))
    p = 2.0 * tail_sum / (2**n)
    return float(min(p, 1.0))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _binary_pass(stat: CaseStat) -> bool:
    """Return True when a CaseStat is majority-passing across k repetitions.

    A case is classified as passing when strictly more than half its
    repetitions pass (passes * 2 > k). For k=1 this equals the single outcome;
    for k=3 a case needs at least 2/3 passes.

    Args:
        stat: The CaseStat to evaluate.
    Returns:
        True if the case is majority-passing, False otherwise.
    """
    return bool(stat.passes * 2 > stat.k)


def _verdict(
    p_value: float,
    improved: int,
    regressed: int,
) -> Literal["better", "worse", "no_detectable_change"]:
    """Map a McNemar p-value and direction counts to a string verdict.

    Args:
        p_value: Two-sided McNemar p-value.
        improved: Count of cases that improved (b→fail, a→pass).
        regressed: Count of cases that regressed (b→pass, a→fail).
    Returns:
        'better' when p < threshold and improved > regressed;
        'worse' when p < threshold and regressed > improved;
        'no_detectable_change' otherwise.
    """
    if p_value >= _SIGNIFICANCE_THRESHOLD:
        return "no_detectable_change"
    if improved > regressed:
        return "better"
    return "worse"


# ---------------------------------------------------------------------------
# paired_compare
# ---------------------------------------------------------------------------


def paired_compare(
    before: tuple[CaseStat, ...],
    after: tuple[CaseStat, ...],
) -> PairedResult:
    """Compare two eval run snapshots using a paired case-level McNemar test.

    Only cases present in both runs (inner join on case_id) contribute to the
    discordant counts. Cases unique to one run are silently excluded; the
    compare verb (EVAL-P8.2) reports them separately.

    Binary pass/fail per case uses majority vote across k repetitions
    (passes * 2 > k), so k=1 uses the single outcome and k=3 requires ≥ 2/3.

    When all matched pairs are concordant (improved + regressed == 0) the
    function short-circuits with p_value=1.0 and 'no_detectable_change',
    avoiding the undefined mcnemar_exact(0, 0) call.

    Args:
        before: CaseStats from the reference run.
        after: CaseStats from the candidate run.
    Returns:
        PairedResult with improved/regressed/unchanged counts, p_value, and verdict.
    """
    before_map: dict[str, CaseStat] = {s.case_id: s for s in before}
    after_map: dict[str, CaseStat] = {s.case_id: s for s in after}

    improved = 0
    regressed = 0
    unchanged = 0

    for case_id, before_stat in before_map.items():
        if case_id not in after_map:
            continue
        after_stat = after_map[case_id]
        before_pass = _binary_pass(before_stat)
        after_pass = _binary_pass(after_stat)
        if not before_pass and after_pass:
            improved += 1
        elif before_pass and not after_pass:
            regressed += 1
        else:
            unchanged += 1

    if improved + regressed == 0:
        return PairedResult(
            improved=improved,
            regressed=regressed,
            unchanged=unchanged,
            p_value=1.0,
            verdict="no_detectable_change",
        )

    p_value = mcnemar_exact(regressed, improved)
    return PairedResult(
        improved=improved,
        regressed=regressed,
        unchanged=unchanged,
        p_value=p_value,
        verdict=_verdict(p_value, improved, regressed),
    )
