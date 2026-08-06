"""
Module: case_stats
Layer: evals (utility)
Purpose: Per-case statistics: CaseStat model, stability classification, and aggregation
         of JudgedRecords by eval slot (record_id) across repetitions.
Dependencies: pydantic, statistics (evals/), eval_records (evals/)
Used by: report generation (EVAL-P2.x onward)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict

from eval_records import JudgedRecord
from statistics import pass_rate, wilson_interval

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Classification = Literal["stable_pass", "flaky", "stable_fail"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STABLE_PASS: Classification = "stable_pass"
_STABLE_FAIL: Classification = "stable_fail"
_FLAKY: Classification = "flaky"

# Lower value = shown earlier in reports (flaky most prominent).
_INSTABILITY_ORDER: dict[Classification, int] = {
    _FLAKY: 0,
    _STABLE_FAIL: 1,
    _STABLE_PASS: 2,
}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class CaseStat(BaseModel):
    """Statistics for one eval slot across k repetitions.

    An eval slot is identified by its record_id (e.g. ``case_001:tone_judge:0``).
    Records with the same record_id but different ``repetition`` values are the
    k runs of that slot; aggregate() groups them here.

    Frozen to ensure immutability after construction.

    Attributes:
        case_id: The record_id shared by all repetitions of this eval slot.
        k: Total repetitions run for this slot.
        passes: Count of repetitions where ``passed`` was True.
        pass_rate: Raw fraction ``passes / k``.
        ci_low: Lower bound of the Wilson 95 % confidence interval.
        ci_high: Upper bound of the Wilson 95 % confidence interval.
        classification: Stability verdict for this slot.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    k: int
    passes: int
    pass_rate: float
    ci_low: float
    ci_high: float
    classification: Classification


# ---------------------------------------------------------------------------
# classify()
# ---------------------------------------------------------------------------


def classify(passes: int, k: int) -> Classification:
    """Return the stability class of a k-repeat eval slot.

    Args:
        passes: Number of passing repetitions (0 ≤ passes ≤ k).
        k: Total repetitions (must be > 0).
    Returns:
        ``"stable_pass"`` when all k pass, ``"stable_fail"`` when none pass,
        ``"flaky"`` for every intermediate result.
    Raises:
        ValueError: When k == 0.
    """
    if k == 0:
        raise ValueError("k must be > 0 to classify a case")
    if passes == k:
        return _STABLE_PASS
    if passes == 0:
        return _STABLE_FAIL
    return _FLAKY


# ---------------------------------------------------------------------------
# aggregate()
# ---------------------------------------------------------------------------


def aggregate(judged_records: Sequence[JudgedRecord]) -> tuple[CaseStat, ...]:
    """Group JudgedRecords by record_id and compute per-slot statistics.

    Groups all records that share a record_id (different repetitions of the
    same eval slot), counts passes, and computes the Wilson 95 % CI and
    stability classification for each slot. Results are sorted by instability
    (flaky slots first, then stable_fail, then stable_pass).

    Args:
        judged_records: Any sequence of JudgedRecords (may span multiple slots
            and repetitions). An empty sequence returns an empty tuple.
    Returns:
        Tuple of CaseStat, one per unique record_id, sorted by instability.
    """
    groups: dict[str, list[JudgedRecord]] = defaultdict(list)
    for record in judged_records:
        groups[record.record_id].append(record)

    stats: list[CaseStat] = []
    for case_id, records in groups.items():
        k = len(records)
        passes = sum(1 for r in records if r.passed)
        rate = pass_rate(passes, k)
        ci_low, ci_high = wilson_interval(passes, k)
        stats.append(
            CaseStat(
                case_id=case_id,
                k=k,
                passes=passes,
                pass_rate=rate,
                ci_low=ci_low,
                ci_high=ci_high,
                classification=classify(passes, k),
            )
        )

    return tuple(sorted(stats, key=lambda s: _INSTABILITY_ORDER[s.classification]))
