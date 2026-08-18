"""
Module: kappa_stats
Layer: evals (utility — statistics only, no eval-domain knowledge)
Purpose: Fleiss kappa for binary multi-rater data, with a case-clustered
         bootstrap confidence interval. Hand-implemented on `random` and
         arithmetic only — no scipy/statsmodels, matching rate_stats.py's
         no-heavy-dependency convention.
Dependencies: dataclasses, random, typing
Used by: panel_metrics (panel agreement), tests/unit/evals/test_panel_metrics.py
Does NOT: know what a judge, record or repetition is — callers hand it vote lists.

WHY KAPPA AND NOT RAW AGREEMENT (DEC-188)
The 2026-08-17 panel run headlined pairwise agreement 0.956 across 345 records.
Because 95.1% of those records pass, two judges that rubber-stamped everything
would have agreed 90.6% by chance alone — so 0.956 sits roughly 5 points above
luck, not 96 points above it. Fleiss kappa rescales that to 0.526 ("moderate").
Publishing only the uncorrected number invites settling EVAL-P21.3 on an
instrument whose noise floor is wider than most A/B effects worth measuring.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

# A rateable item needs at least this many non-inconclusive votes; a single vote
# cannot agree or disagree with anything.
_MIN_VOTES_PER_ITEM: int = 2

# Clustered bootstrap settings. Resampling is done over CLUSTERS, not items: the
# k repeats and the several criteria of one eval case are not independent
# observations, and resampling items directly would understate the interval.
# Mirrors calibration.py's case-clustered approach.
_BOOTSTRAP_SAMPLES: int = 2000
_BOOTSTRAP_SEED: int = 20260818
_CI_LOW_PCT: float = 2.5
_CI_HIGH_PCT: float = 97.5

# Below this share of resamples yielding a defined kappa, no interval is
# reported rather than one built from a biased subset.
_MIN_DEFINED_RESAMPLE_RATIO: float = 0.5


@dataclass(frozen=True)
class KappaResult:
    """Fleiss kappa for a set of items, with the pieces it decomposes into.

    Attributes:
        kappa: Chance-corrected agreement, or None when undefined.
        observed_agreement: Mean per-item agreement (Pbar) — the raw number.
        chance_agreement: Agreement expected from the marginals alone (Pe).
        n_items: Rateable items (>= 2 available votes).
        ci_low: Lower bound of the clustered bootstrap 95% CI, when computed.
        ci_high: Upper bound of the clustered bootstrap 95% CI, when computed.
        undefined_reason: Why kappa is None; empty when kappa is defined.
    """

    kappa: float | None
    observed_agreement: float
    chance_agreement: float
    n_items: int
    ci_low: float | None = None
    ci_high: float | None = None
    undefined_reason: str = ""


def rateable(items: Sequence[Sequence[bool | None]]) -> list[list[bool]]:
    """Drop inconclusive votes and any item left with too few to compare.

    Args:
        items: One sequence of per-rater votes per item (True/False/None).
    Returns:
        Only the items retaining at least two real votes.
    """
    kept = []
    for votes in items:
        available = [v for v in votes if v is not None]
        if len(available) >= _MIN_VOTES_PER_ITEM:
            kept.append(available)
    return kept


def fleiss_kappa(items: Sequence[Sequence[bool | None]]) -> KappaResult:
    """Compute Fleiss kappa over binary per-item vote lists.

    Handles the ragged case (items with differing rater counts, after
    inconclusive votes are dropped) by computing each item's agreement
    proportion against its own available-rater count.

    Args:
        items: One sequence of per-rater votes per item (True/False/None).
    Returns:
        KappaResult; kappa is None when every vote falls in one category (no
        variance to correct against) or when there are no rateable items.
    """
    kept = rateable(items)
    if not kept:
        return KappaResult(
            kappa=None,
            observed_agreement=0.0,
            chance_agreement=0.0,
            n_items=0,
            undefined_reason="no items with at least two available votes",
        )

    agreements = []
    n_true = 0
    n_votes = 0
    for votes in kept:
        n = len(votes)
        t = sum(1 for v in votes if v)
        f = n - t
        agreements.append((t * (t - 1) + f * (f - 1)) / (n * (n - 1)))
        n_true += t
        n_votes += n

    observed = sum(agreements) / len(kept)
    p_true = n_true / n_votes
    chance = p_true * p_true + (1.0 - p_true) * (1.0 - p_true)

    if chance >= 1.0:
        return KappaResult(
            kappa=None,
            observed_agreement=observed,
            chance_agreement=chance,
            n_items=len(kept),
            undefined_reason="every vote fell in one category — no variance to chance-correct",
        )

    return KappaResult(
        kappa=(observed - chance) / (1.0 - chance),
        observed_agreement=observed,
        chance_agreement=chance,
        n_items=len(kept),
    )


def _percentile(values: list[float], pct: float) -> float:
    """Return the linear-interpolated percentile of a list of floats."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * pct / 100.0
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def bootstrap_kappa_ci(
    clusters: Sequence[Sequence[Sequence[bool | None]]],
) -> tuple[float | None, float | None]:
    """Clustered bootstrap CI for Fleiss kappa, resampling whole clusters.

    Deterministic: seeded with _BOOTSTRAP_SEED so a re-run of the same data
    reproduces the same interval (the harness logs seeds for exactly this reason).

    Args:
        clusters: One list of item vote-lists per cluster (an eval case).
    Returns:
        (ci_low, ci_high), or (None, None) when there are too few clusters or
        kappa is undefined in too many resamples to form an interval.
    """
    if len(clusters) < 2:
        return (None, None)

    rng = random.Random(_BOOTSTRAP_SEED)
    kappas: list[float] = []
    for _ in range(_BOOTSTRAP_SAMPLES):
        drawn: list[Sequence[bool | None]] = []
        for _ in range(len(clusters)):
            drawn.extend(clusters[rng.randrange(len(clusters))])
        result = fleiss_kappa(drawn)
        if result.kappa is not None:
            kappas.append(result.kappa)

    if len(kappas) < _BOOTSTRAP_SAMPLES * _MIN_DEFINED_RESAMPLE_RATIO:
        return (None, None)
    return (_percentile(kappas, _CI_LOW_PCT), _percentile(kappas, _CI_HIGH_PCT))
