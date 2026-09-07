"""
Module: case_stats
Layer: evals (utility)
Purpose: Per-case statistics: CaseStat model, stability classification, and aggregation
         of JudgedRecords by eval slot (record_id) across repetitions.
Dependencies: pydantic, rate_stats (evals/), eval_records (evals/)
Used by: report generation (EVAL-P2.x onward)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict

from eval_records import JudgedRecord
from rate_stats import pass_rate, wilson_interval

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Classification = Literal["stable_pass", "flaky", "stable_fail"]
Battery = Literal["guard", "capability", "excluded"]

#: The two populations inside the guard battery, which are graded by different expectation
#: sets and therefore never share a rate (DEC-243).
GuardPopulation = Literal["adversarial", "anti_hallucination"]

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

# The guard battery is TWO populations graded by different expectation sets (DEC-243).
# They are named separately because a rate over their union is not a quantity: averaging
# two grading contracts produces a number with no referent. `case_adv_`/`case_neg_` are
# scored on the YAML battery's tone_judge / affirms_judge / schema / keyword_none /
# min_length; `ah_demo_` is scored on affirms_judge / anti_hallucination_grounded
# (refusal_judge before measurement-remediation Phase 2c, DEC-269 — retired and folded
# into affirms_judge), which are purpose-built anti-hallucination expectations.
# Measured on k3_77688e7_regen1 (pre-Phase-2c corpus) the two
# sit 6.4 pp apart (0.8468 over n=111 vs 0.9106 over n=123), so the union was not a
# harmless convenience: the easier battery is more than half the denominator and lifted the
# published figure ~3.4 pp above the adversarial battery alone.
_ADVERSARIAL_PREFIXES: tuple[str, ...] = ("case_adv_", "case_neg_")
_ANTI_HALLUCINATION_PREFIXES: tuple[str, ...] = ("ah_demo_",)

# Union, for the one question that is legitimately about both: "is this a guard case at
# all", which decides guard-vs-capability-vs-excluded. Never use it to build a RATE.
_GUARD_PREFIXES: tuple[str, ...] = _ADVERSARIAL_PREFIXES + _ANTI_HALLUCINATION_PREFIXES
_CAPABILITY_PREFIX: str = "case_pos_"
# Cases that belong to no published battery: counted explicitly but excluded from all rates.
# Specific artifact prefixes are named first for documentation; "case_" catches any other
# case_xxx_* ID that hasn't been assigned a battery yet, including synthetic test fixtures.
# Battery-specific prefixes (case_adv_*, case_neg_*, ah_demo_*, case_pos_*) are checked
# BEFORE this list and are never matched here.
_EXCLUDED_PREFIXES: tuple[str, ...] = (
    "case_001_",
    "case_002_",
    "case_003_",
    "case_voice_",
    "moderation_",
    "reputation_",
    "test_",
    "case_",
)


# ---------------------------------------------------------------------------
# Battery classification
# ---------------------------------------------------------------------------


def classify_battery(case_id: str) -> Battery:
    """Classify a case_id as guard, capability, or excluded.

    Args:
        case_id: The case identifier string.
    Returns:
        ``'guard'`` for adversarial/negative/ah_demo cases;
        ``'capability'`` for case_pos_* cases;
        ``'excluded'`` for known non-battery case prefixes in the artifact.
    Raises:
        ValueError: When ``case_id`` matches no known prefix — it must never be
            silently dropped into any rate denominator.
    """
    if case_id.startswith(_GUARD_PREFIXES):
        return "guard"
    if case_id.startswith(_CAPABILITY_PREFIX):
        return "capability"
    if case_id.startswith(_EXCLUDED_PREFIXES):
        return "excluded"
    raise ValueError(
        f"Case '{case_id}' matches no known battery prefix "
        f"(guard: case_adv_*/case_neg_*/ah_demo_*, "
        f"capability: case_pos_*, excluded: {_EXCLUDED_PREFIXES})"
    )


def guard_population(case_id: str) -> GuardPopulation:
    """Say which of the two guard populations a guard case belongs to (DEC-243).

    The two are scored by different expectation sets, so any rate must be computed within
    one of them. `classify_battery` answers "is this a guard case"; this answers "graded
    how", and the pair of answers is what keeps the published rates from re-merging.

    Args:
        case_id: The case identifier string.
    Returns:
        ``'adversarial'`` for case_adv_*/case_neg_*; ``'anti_hallucination'`` for ah_demo_*.
    Raises:
        ValueError: When ``case_id`` is not a guard case at all. Returning a default here
            would silently absorb capability or excluded cases into a guard rate, which is
            the conflation this split exists to remove.
    """
    if case_id.startswith(_ADVERSARIAL_PREFIXES):
        return "adversarial"
    if case_id.startswith(_ANTI_HALLUCINATION_PREFIXES):
        return "anti_hallucination"
    raise ValueError(
        f"Case '{case_id}' is not a guard case, so it has no guard population "
        f"(adversarial: case_adv_*/case_neg_*, anti-hallucination: ah_demo_*)"
    )


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
