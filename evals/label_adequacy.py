"""
Module: label_adequacy
Layer: evals (eval harness — not part of src/)
Purpose: Count-based policy deciding whether a scorer's human labels can support a
         kappa estimate at all. Encodes policy as a function so a scorer's kappa is
         never computed — let alone printed or trended — from a label set the
         cluster bootstrap cannot support (DEC-260).
Dependencies: calibration_records (CalibrationLabel), dataclasses, typing
Used by: evals/calibration.py (run_calibration), scripts/check_label_adequacy.py,
         tests/unit/evals/test_label_adequacy.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from calibration_records import CalibrationLabel

# ---------------------------------------------------------------------------
# Constants — v1 floor. A count check, not a power analysis (DEC-260).
# ---------------------------------------------------------------------------

MIN_MINORITY_LABELS: int = 25
"""Fewest labels the smaller of the two human-verdict classes may have.

Below this the confusion matrix itself carries too little information about the
minority class to trust a kappa computed from it — measured 2026-09-04: the four
scorers in the committed corpus have 7, 8, 8 and 11 minority items respectively.
"""

MIN_CASE_CLUSTERS: int = 10
"""Fewest distinct case clusters (record_id's case_id) a scorer's labels must span.

calibration.kappa_interval resamples by case cluster (calibration._extract_case_clusters),
not by row — a resample that misses the few clusters carrying the minority class goes
degenerate. This arm bounds that independently of how many labels exist in total: 393
labels concentrated in a handful of clusters would still produce a bootstrap with too
few independent draws.
"""


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdequacyRefusal:
    """Returned when a scorer's labels cannot support a kappa estimate.

    Attributes:
        scorer: Identifier of the scorer being checked.
        minority_n: Count of the smaller human-verdict class among clean adjudicated
            rows (needs_review excluded, mirroring calibration._adjudicated_rows).
        n_clusters: Total distinct case clusters those rows span.
        reason: Human-readable explanation naming both counts and both floors, meant
            to be printed directly in place of a kappa.
    """

    scorer: str
    minority_n: int
    n_clusters: int
    reason: str


# ---------------------------------------------------------------------------
# Policy function
# ---------------------------------------------------------------------------


def _clean_adjudicated(rows: Sequence[CalibrationLabel]) -> list[CalibrationLabel]:
    """Rows with a human verdict, excluding drifted (needs_review) ones.

    Mirrors calibration._adjudicated_rows: a drifted row carries a human verdict
    recorded against text the scorer no longer produces, and every calibration
    statistic — including this adequacy check — must exclude it.
    """
    return [r for r in rows if r.human_verdict is not None and not r.needs_review]


def _minority_count(rows: Sequence[CalibrationLabel]) -> int:
    """Count of the smaller of the True/False human-verdict classes."""
    true_n = sum(1 for r in rows if r.human_verdict is True)
    false_n = sum(1 for r in rows if r.human_verdict is False)
    return min(true_n, false_n)


def _cluster_count(rows: Sequence[CalibrationLabel]) -> int:
    """Count of distinct case clusters, mirroring calibration._extract_case_clusters."""
    return len({r.record_id.split(":")[0] for r in rows})


def check_label_adequacy(
    scorer: str,
    rows: Sequence[CalibrationLabel],
) -> AdequacyRefusal | None:
    """Return a refusal if the scorer's labels cannot support a kappa estimate.

    Two independent floors on the clean adjudicated rows (needs_review excluded):
    the minority human-verdict class must have at least MIN_MINORITY_LABELS items,
    and the rows together must span at least MIN_CASE_CLUSTERS case clusters.
    Either floor unmet refuses. v1 is a count check — no power analysis, and the
    bootstrap itself (calibration.kappa_interval) is untouched.

    Args:
        scorer: Identifier of the scorer being checked.
        rows: This scorer's CalibrationLabel rows (may include other scorers' rows;
            only rows matching `scorer` are considered).
    Returns:
        None when both floors are cleared; an AdequacyRefusal otherwise.
    """
    clean = _clean_adjudicated([r for r in rows if r.scorer == scorer])
    minority_n = _minority_count(clean)
    n_clusters = _cluster_count(clean)
    if minority_n >= MIN_MINORITY_LABELS and n_clusters >= MIN_CASE_CLUSTERS:
        return None
    return AdequacyRefusal(
        scorer=scorer,
        minority_n=minority_n,
        n_clusters=n_clusters,
        reason=(
            f"insufficient labels: {minority_n} minority items across {n_clusters} "
            f"clusters (need >={MIN_MINORITY_LABELS} across >={MIN_CASE_CLUSTERS})"
        ),
    )
