"""
Module: test_label_adequacy
Layer: test (unit)
Purpose: Unit tests for label_adequacy.py — the count-based floor that decides
         whether a scorer's human labels can support a kappa estimate at all
         (DEC-260). Kappa's cluster bootstrap goes degenerate when the minority
         human-verdict class is too small or too concentrated in a few case
         clusters; this policy refuses calibration before that number is ever
         printed or trended, rather than after.
Dependencies: pytest, calibration_records (CalibrationLabel), label_adequacy (evals/)
Used by: pytest (make test / make check); scripts/check_label_adequacy.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from calibration_records import CalibrationLabel, read_calibration_labels
from label_adequacy import AdequacyRefusal, check_label_adequacy

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LABELS_PATH = _REPO_ROOT / "evals" / "calibration" / "labels_v1.jsonl"


def _label(
    i: int,
    scorer: str = "tone_judge",
    *,
    human_verdict: bool | None,
    case_id: str | None = None,
) -> CalibrationLabel:
    """One minimal adjudicated CalibrationLabel row for adequacy fixtures."""
    return CalibrationLabel(
        record_id=f"{case_id or f'case_{i:03d}'}:{scorer}:0",
        scorer=scorer,
        output_text=f"output {i}",
        scorer_verdict=True,
        pre_label=True,
        pre_labeller_model="claude-opus-5",
        human_verdict=human_verdict,
        adjudicated_at="2026-09-01T00:00:00Z",
        notes="",
    )


def _clustered_rows(
    *, majority_clusters: int, minority_clusters: int, reps_per_cluster: int = 1
) -> list[CalibrationLabel]:
    """Rows spread over distinct case clusters, split by human_verdict majority/minority."""
    rows: list[CalibrationLabel] = []
    i = 0
    for c in range(majority_clusters):
        for _ in range(reps_per_cluster):
            rows.append(_label(i, human_verdict=True, case_id=f"maj_{c:03d}"))
            i += 1
    for c in range(minority_clusters):
        for _ in range(reps_per_cluster):
            rows.append(_label(i, human_verdict=False, case_id=f"min_{c:03d}"))
            i += 1
    return rows


# ---------------------------------------------------------------------------
# RED anchor — must fail before the policy is implemented
# ---------------------------------------------------------------------------


def test_the_real_tone_judge_labels_are_refused() -> None:
    """RED anchor. Measured 2026-09-04: tone_judge has 7 minority (human=False)
    items across 3 of its 45 total case clusters — kappa 0.849 with a 95% CI of
    [-0.010, 1.000]. That CI is not a bug; it correctly reports that 7 items
    cannot support a kappa estimate. This must be refused before it is computed."""
    if not _LABELS_PATH.exists():
        pytest.skip("real committed labels not present in this checkout")
    labels = read_calibration_labels(_LABELS_PATH)
    tone_rows = [r for r in labels if r.scorer == "tone_judge"]

    refusal = check_label_adequacy("tone_judge", tone_rows)

    assert refusal is not None, "Expected a refusal for tone_judge's real labels but got None"
    assert isinstance(refusal, AdequacyRefusal)
    assert refusal.scorer == "tone_judge"
    assert refusal.minority_n == 7
    assert refusal.n_clusters == 45
    assert "7" in refusal.reason
    assert "45" in refusal.reason


# ---------------------------------------------------------------------------
# Additional policy tests (GREEN)
# ---------------------------------------------------------------------------


def test_adequate_labels_are_not_refused() -> None:
    """Both floors cleared: 30 minority items (>= 25) across 40 total clusters (>= 10)."""
    rows = _clustered_rows(majority_clusters=40, minority_clusters=30)
    assert check_label_adequacy("tone_judge", rows) is None


def test_too_few_minority_items_is_refused() -> None:
    """24 minority items (one below the floor) across plenty of clusters is still refused."""
    rows = _clustered_rows(majority_clusters=40, minority_clusters=24)
    refusal = check_label_adequacy("tone_judge", rows)
    assert refusal is not None
    assert refusal.minority_n == 24


def test_too_few_total_clusters_is_refused_even_with_enough_minority_items() -> None:
    """30 minority items clear MIN_MINORITY_LABELS, but they all sit in ONE cluster
    (repeated generations of the same case), and only 9 total clusters exist (< 10)."""
    minority_rows = [
        CalibrationLabel(
            record_id=f"min_case:tone_judge:{i}",
            scorer="tone_judge", output_text=f"output {i}", scorer_verdict=True,
            pre_label=True, pre_labeller_model="claude-opus-5", human_verdict=False,
            adjudicated_at="2026-09-01T00:00:00Z", notes="",
        )
        for i in range(30)
    ]
    majority_rows = [
        _label(100 + i, human_verdict=True, case_id=f"maj_{i % 8:03d}") for i in range(40)
    ]
    refusal = check_label_adequacy("tone_judge", minority_rows + majority_rows)
    assert refusal is not None
    assert refusal.minority_n == 30  # the minority arm clears the floor on its own
    assert refusal.n_clusters == 9  # 1 minority cluster + 8 majority clusters — the cluster arm fails


def test_needs_review_rows_are_excluded_like_calibration_does() -> None:
    """A needs_review row must not count toward either floor — it mirrors
    calibration._adjudicated_rows, which excludes drifted rows from every statistic."""
    minority_rows = [_label(i, human_verdict=False, case_id=f"min_{i:03d}") for i in range(25)]
    majority_rows = [_label(100 + i, human_verdict=True, case_id=f"maj_{i:03d}") for i in range(40)]
    assert check_label_adequacy("tone_judge", minority_rows + majority_rows) is None

    drifted = minority_rows[0].model_copy(update={"needs_review": True})
    refusal = check_label_adequacy("tone_judge", [drifted] + minority_rows[1:] + majority_rows)
    assert refusal is not None
    assert refusal.minority_n == 24  # one of the 25 minority rows was excluded as drifted


def test_unadjudicated_rows_do_not_count() -> None:
    """A row with human_verdict=None (not yet adjudicated) counts toward neither class."""
    rows = _clustered_rows(majority_clusters=40, minority_clusters=30)
    pending = _label(999, human_verdict=None, case_id="pending_case")
    refusal = check_label_adequacy("tone_judge", rows + [pending])
    assert refusal is None  # the pending row neither helps nor hurts either floor

