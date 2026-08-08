"""
Module: test_calibration
Layer: test (unit)
Purpose: Unit tests for calibration.py — confusion matrices, Cohen's κ with
         bootstrap CI, and per-scorer calibration reports (EVAL-P5.4/P5.5).
         Covers both the headline axis (scorer_verdict vs human_verdict) and
         the secondary axis (pre_label vs human_verdict).
Dependencies: pytest, calibration_records, calibration (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import random

import pytest

from calibration_records import CalibrationLabel
from calibration import (
    ConfusionCounts,
    agreement_rate,
    cohens_kappa,
    confusion_counts,
    kappa_interval,
    precision,
    recall,
)

_LABELLER = "claude-opus-5"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _label(
    i: int,
    *,
    pre_label: bool,
    scorer_verdict: bool | None = None,
    human_verdict: bool | None = None,
    scorer: str = "tone_judge",
) -> CalibrationLabel:
    """Build a CalibrationLabel for testing.

    scorer_verdict defaults to pre_label when omitted so existing tests that
    set pre_label to mirror the confusion matrix continue to work unchanged.
    """
    return CalibrationLabel(
        record_id=f"case_{i:03d}:{scorer}:0",
        scorer=scorer,
        output_text=f"Output for row {i}.",
        scorer_verdict=scorer_verdict if scorer_verdict is not None else pre_label,
        pre_label=pre_label,
        pre_labeller_model=_LABELLER,
        human_verdict=human_verdict,
        adjudicated_at="2026-08-07T10:00:00+00:00" if human_verdict is not None else None,
        notes="",
    )


def _make_rows_from_matrix(
    *,
    tp: int,
    fp: int,
    fn: int,
    tn: int,
    scorer: str = "tone_judge",
) -> list[CalibrationLabel]:
    """Build adjudicated CalibrationLabel rows from a confusion matrix.

    Maps the matrix to BOTH scorer_verdict and pre_label so the headline
    (scorer_verdict vs human_verdict) and secondary (pre_label vs human_verdict)
    confusion matrices are identical. Tests that check a single κ value remain valid.

    TP: scorer_verdict=pre_label=True,  human_verdict=True
    FP: scorer_verdict=pre_label=True,  human_verdict=False  (dangerous)
    FN: scorer_verdict=pre_label=False, human_verdict=True
    TN: scorer_verdict=pre_label=False, human_verdict=False
    """
    rows: list[CalibrationLabel] = []
    i = 0
    for _ in range(tp):
        rows.append(_label(i, pre_label=True, human_verdict=True, scorer=scorer))
        i += 1
    for _ in range(fp):
        rows.append(_label(i, pre_label=True, human_verdict=False, scorer=scorer))
        i += 1
    for _ in range(fn):
        rows.append(_label(i, pre_label=False, human_verdict=True, scorer=scorer))
        i += 1
    for _ in range(tn):
        rows.append(_label(i, pre_label=False, human_verdict=False, scorer=scorer))
        i += 1
    return rows


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_cohens_kappa_matches_worked_example() -> None:
    """κ matches a hand-worked 2×2 table to 3 decimal places.

    Worked example:
        TP=4, FP=1, FN=2, TN=3  (N=10)
        Po = (4+3)/10 = 0.7
        p_yes_model = (4+1)/10 = 0.5
        p_yes_human = (4+2)/10 = 0.6
        p_no_model  = (2+3)/10 = 0.5
        p_no_human  = (1+3)/10 = 0.4
        Pe = 0.5*0.6 + 0.5*0.4 = 0.3 + 0.2 = 0.5
        κ  = (0.7 - 0.5) / (1 - 0.5) = 0.400
    """
    rows = _make_rows_from_matrix(tp=4, fp=1, fn=2, tn=3)
    kappa = cohens_kappa(rows)
    assert round(kappa, 3) == 0.400


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_perfect_agreement_yields_kappa_one() -> None:
    """Perfect agreement → κ = 1.000."""
    rows = _make_rows_from_matrix(tp=5, fp=0, fn=0, tn=5)
    assert round(cohens_kappa(rows), 3) == 1.000


def test_chance_level_yields_kappa_zero() -> None:
    """Chance-level agreement (Po = Pe) → κ = 0.000.

    Balanced disagreement: TP=FP=FN=TN=1 (N=4)
    Po = 0.5, Pe = 0.5, κ = 0.0.
    """
    rows = _make_rows_from_matrix(tp=1, fp=1, fn=1, tn=1)
    assert round(cohens_kappa(rows), 3) == 0.000


def test_confusion_counts_correct() -> None:
    """confusion_counts tallies TP/FP/FN/TN correctly."""
    rows = _make_rows_from_matrix(tp=4, fp=1, fn=2, tn=3)
    counts = confusion_counts(rows)
    assert counts.tp == 4
    assert counts.fp == 1
    assert counts.fn == 2
    assert counts.tn == 3


def test_confusion_counts_excludes_unadjudicated() -> None:
    """Only adjudicated rows (human_verdict is not None) are counted."""
    rows = _make_rows_from_matrix(tp=2, fp=1, fn=1, tn=2)
    rows.append(_label(100, pre_label=True, human_verdict=None))
    counts = confusion_counts(rows)
    assert counts.tp + counts.fp + counts.fn + counts.tn == 6


def test_precision_and_recall() -> None:
    """precision=TP/(TP+FP), recall=TP/(TP+FN)."""
    counts = ConfusionCounts(tp=4, fp=1, fn=2, tn=3)
    assert round(precision(counts), 3) == round(4 / 5, 3)
    assert round(recall(counts), 3) == round(4 / 6, 3)


def test_precision_no_predicted_positives_returns_one() -> None:
    """precision returns 1.0 when no positives are predicted (avoid ZeroDivisionError)."""
    counts = ConfusionCounts(tp=0, fp=0, fn=3, tn=2)
    assert precision(counts) == 1.0


def test_recall_no_ground_truth_positives_returns_one() -> None:
    """recall returns 1.0 when no ground-truth positives exist."""
    counts = ConfusionCounts(tp=0, fp=2, fn=0, tn=3)
    assert recall(counts) == 1.0


def test_agreement_rate_pre_label_vs_human() -> None:
    """agreement_rate = rows where pre_label == human_verdict / total adjudicated."""
    rows = _make_rows_from_matrix(tp=4, fp=1, fn=2, tn=3)
    # TP (4) + TN (3) = 7 rows agree out of 10
    assert round(agreement_rate(rows), 3) == 0.700


def test_kappa_interval_is_seeded_and_reproducible() -> None:
    """kappa_interval with same rows and seed returns identical bounds across calls."""
    rows = _make_rows_from_matrix(tp=4, fp=1, fn=2, tn=3)
    bounds_a = kappa_interval(rows, resamples=200, seed=42)
    bounds_b = kappa_interval(rows, resamples=200, seed=42)
    assert bounds_a == bounds_b


def test_kappa_interval_different_seeds_differ() -> None:
    """Different seeds produce different intervals."""
    rows = _make_rows_from_matrix(tp=4, fp=1, fn=2, tn=3)
    bounds_a = kappa_interval(rows, resamples=200, seed=42)
    bounds_b = kappa_interval(rows, resamples=200, seed=99)
    assert bounds_a != bounds_b


def test_kappa_interval_is_valid_range() -> None:
    """Bootstrap interval is a valid range: lo ≤ hi and both in [-1, 1]."""
    rows = _make_rows_from_matrix(tp=4, fp=1, fn=2, tn=3)
    lo, hi = kappa_interval(rows, resamples=200, seed=42)
    assert -1.0 <= lo <= hi <= 1.0


def test_kappa_interval_wide_at_85_rows() -> None:
    """At ~85 rows a noisy scorer produces a visibly wide CI (width ≥ 0.10).

    Bootstrap SE at n≈85 is ~±0.10, so a realistic noisy scorer yields
    a total CI width ≥ 0.10.
    """
    rng = random.Random(0)
    rows = []
    for i in range(85):
        pre = rng.random() > 0.4
        human = pre if rng.random() > 0.25 else not pre
        rows.append(_label(i, pre_label=pre, human_verdict=human))
    lo, hi = kappa_interval(rows, resamples=2000, seed=42)
    assert hi - lo >= 0.10


# ---------------------------------------------------------------------------
# EVAL-P5.5 RED anchor
# ---------------------------------------------------------------------------


def test_headline_matrix_compares_scorer_verdict_to_human() -> None:
    """Headline κ compares scorer_verdict to human_verdict; secondary compares pre_label.

    Fixture: scorer agrees 9/10 with human; pre_label agrees 10/10.
      scorer vs human   → TP=9, FP=1, FN=0, TN=0
      pre_label vs human → TP=9, FP=0, FN=0, TN=1
    The two kappa values must differ; the FP cell must read
    'scorer said pass, human said fail'.
    """
    from calibration import _print_scorer_report, calibrate_scorer

    rows = [
        CalibrationLabel(
            record_id=f"case_{i:03d}:tone_judge:0",
            scorer="tone_judge",
            output_text=f"output {i}",
            scorer_verdict=True,
            pre_label=True,
            pre_labeller_model=_LABELLER,
            human_verdict=True,
            adjudicated_at="2026-08-07T10:00:00+00:00",
            notes="",
        )
        for i in range(9)
    ]
    rows.append(
        CalibrationLabel(
            record_id="case_009:tone_judge:0",
            scorer="tone_judge",
            output_text="output 9",
            scorer_verdict=True,
            pre_label=False,
            pre_labeller_model=_LABELLER,
            human_verdict=False,
            adjudicated_at="2026-08-07T10:00:00+00:00",
            notes="",
        )
    )
    assert rows[0].scorer_verdict is True  # RED: AttributeError until field is added

    report = calibrate_scorer("tone_judge", rows)
    assert report.kappa != report.pre_label_kappa

    lines: list[str] = []
    _print_scorer_report(report, print_fn=lines.append)
    assert any("scorer said pass" in ln and "human said fail" in ln for ln in lines)
