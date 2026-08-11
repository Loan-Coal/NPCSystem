"""
Module: test_calibration
Layer: test (unit)
Purpose: Unit tests for calibration.py — confusion matrices, Cohen's κ with
         bootstrap CI, and per-scorer calibration reports (EVAL-P5.4/P5.5).
         Covers both the headline axis (scorer_verdict vs human_verdict) and
         the secondary axis (pre_label vs human_verdict).
         EVAL-P16.2: cluster bootstrap resamples cases, not individual rows.
Dependencies: pytest, calibration_records, calibration (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import random

import pytest

from calibration_records import CalibrationLabel
from calibration import (
    ConfusionCounts,
    KappaCI,
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


def test_precision_no_predicted_positives_returns_none() -> None:
    """precision returns None when no positives are predicted (TP+FP=0)."""
    counts = ConfusionCounts(tp=0, fp=0, fn=3, tn=2)
    assert precision(counts) is None


def test_recall_no_ground_truth_positives_returns_none() -> None:
    """recall returns None when no ground-truth positives exist (TP+FN=0)."""
    counts = ConfusionCounts(tp=0, fp=2, fn=0, tn=3)
    assert recall(counts) is None


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
    ci = kappa_interval(rows, resamples=200, seed=42)
    assert -1.0 <= ci.lo <= ci.hi <= 1.0


def test_kappa_interval_wide_at_85_rows() -> None:
    """At ~85 rows a noisy scorer produces a visibly wide CI (width ≥ 0.10).

    Bootstrap SE at n≈85 is ~±0.10, so a realistic noisy scorer yields
    a total CI width ≥ 0.10. Each row has a unique case_id so cluster
    bootstrap equals row bootstrap here (n_clusters == n_rows).
    """
    rng = random.Random(0)
    rows = []
    for i in range(85):
        pre = rng.random() > 0.4
        human = pre if rng.random() > 0.25 else not pre
        rows.append(_label(i, pre_label=pre, human_verdict=human))
    ci = kappa_interval(rows, resamples=2000, seed=42)
    assert ci.hi - ci.lo >= 0.10
    # Each _label uses a unique case_i prefix so clusters == rows
    assert ci.n_clusters == ci.n_rows


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


# ---------------------------------------------------------------------------
# EVAL-P16.2 RED anchor
# ---------------------------------------------------------------------------


def _make_clustered_rows(
    *,
    good_cases: int,
    bad_cases: int,
    reps_per_case: int,
    scorer: str = "tone_judge",
) -> list[CalibrationLabel]:
    """Build clustered CalibrationLabel rows.

    Good cases: all rows are TP (scorer=True, human=True).
    Bad cases: all rows are FP (scorer=True, human=False).
    Each case has `reps_per_case` rows sharing the same case_id prefix.
    """
    rows: list[CalibrationLabel] = []
    for c in range(good_cases):
        for r in range(reps_per_case):
            rows.append(
                CalibrationLabel(
                    record_id=f"good_{c:02d}:{scorer}:0#r{r}",
                    scorer=scorer,
                    output_text=f"good case {c} rep {r}",
                    scorer_verdict=True,
                    pre_label=True,
                    pre_labeller_model=_LABELLER,
                    human_verdict=True,
                    adjudicated_at="2026-08-11T10:00:00+00:00",
                    notes="",
                )
            )
    for c in range(bad_cases):
        for r in range(reps_per_case):
            rows.append(
                CalibrationLabel(
                    record_id=f"bad_{c:02d}:{scorer}:0#r{r}",
                    scorer=scorer,
                    output_text=f"bad case {c} rep {r}",
                    scorer_verdict=True,
                    pre_label=True,
                    pre_labeller_model=_LABELLER,
                    human_verdict=False,
                    adjudicated_at="2026-08-11T10:00:00+00:00",
                    notes="",
                )
            )
    return rows


def test_bootstrap_resamples_cases_not_rows() -> None:
    """kappa_interval resamples by case cluster, not by individual row.

    Fixture: 3 all-TP cases + 1 all-FP case, 3 reps each (12 rows, 4 cases).

    The result must be a KappaCI with n_clusters=4 (not 12).
    Row-level bootstrap would draw from 12 rows, clustering from 4 cases —
    the CI must be wider under case-level resampling because each drawn FP
    cluster contributes 3 correlated failures at once.

    The interval must cover κ=0 (chance level) since the bad case dominates
    ~25% of resample draws when it appears multiple times.
    """
    rows = _make_clustered_rows(good_cases=3, bad_cases=1, reps_per_case=3)
    result = kappa_interval(rows, resamples=2000, seed=42)

    assert isinstance(result, KappaCI)
    assert result.n_clusters == 4   # 4 cases, not 12 rows
    assert result.n_rows == 12
    # CI is wider than [0, 1] → must include chance (lo ≤ 0)
    assert result.lo <= 0.0, (
        f"Expected CI to include chance (κ=0) with only 4 clusters, got lo={result.lo:.3f}"
    )


# ---------------------------------------------------------------------------
# EVAL-P16.3 RED anchor
# ---------------------------------------------------------------------------


def test_degenerate_single_class_matrix_raises_rather_than_returning_one() -> None:
    """_kappa_from_matrix raises UndefinedKappaError when Pe=1 (all-agree matrix).

    A 60-row all-TP matrix: Pe = (60/60)*(60/60) + 0 = 1.0.
    κ = (Po - Pe) / (1 - Pe) = 0/0 — undefined, not 1.0.
    The error must name Pe and cell counts so callers can diagnose the state.
    """
    from calibration import UndefinedKappaError, _kappa_from_matrix

    with pytest.raises(UndefinedKappaError) as exc_info:
        _kappa_from_matrix(tp=60, fp=0, fn=0, tn=0)

    err_str = str(exc_info.value)
    assert "Pe" in err_str, f"Error must name Pe; got: {err_str}"
    assert "tp" in err_str or "60" in err_str, f"Error must name cell counts; got: {err_str}"

    # cohens_kappa propagates the error for a 60-row all-TP population
    rows = _make_rows_from_matrix(tp=60, fp=0, fn=0, tn=0)
    with pytest.raises(UndefinedKappaError):
        cohens_kappa(rows)


def test_precision_returns_none_on_empty_denominator() -> None:
    """precision returns None (not 1.0) when no positives are predicted (TP+FP=0)."""
    counts = ConfusionCounts(tp=0, fp=0, fn=3, tn=2)
    assert precision(counts) is None


def test_recall_returns_none_on_empty_denominator() -> None:
    """recall returns None (not 1.0) when no ground-truth positives exist (TP+FN=0)."""
    counts = ConfusionCounts(tp=0, fp=2, fn=0, tn=3)
    assert recall(counts) is None


# ---------------------------------------------------------------------------
# EVAL-P16.5 RED anchors
# ---------------------------------------------------------------------------


def test_calibration_report_names_family_size_and_holm_ci() -> None:
    """run_calibration output names the family size and Holm-adjusted companion CIs.

    One scorer → family_size = 2 (headline κ CI + secondary κ CI).
    Output must include 'family' and 'holm' (case-insensitive).
    """
    from calibration import run_calibration

    rows = _make_rows_from_matrix(tp=4, fp=1, fn=2, tn=3)
    lines: list[str] = []
    run_calibration(rows, print_fn=lines.append)
    full_output = "\n".join(lines)
    assert "family" in full_output.lower(), (
        f"Expected 'family' in calibration output; got:\n{full_output}"
    )
    assert "holm" in full_output.lower(), (
        f"Expected 'holm' in calibration output; got:\n{full_output}"
    )


def test_holm_ci_is_wider_than_nominal() -> None:
    """kappa_interval with family_size=8 returns Holm-adjusted CI wider than nominal.

    At family_size=8 α*=0.05/8=0.00625. The Holm bounds must satisfy
    holm_lo ≤ lo and holm_hi ≥ hi; both must be non-None.
    """
    rows = _make_rows_from_matrix(tp=4, fp=1, fn=2, tn=3)
    ci = kappa_interval(rows, resamples=2000, seed=42, family_size=8)
    assert ci.holm_lo is not None, "holm_lo should be set when family_size=8"
    assert ci.holm_hi is not None, "holm_hi should be set when family_size=8"
    assert ci.holm_lo <= ci.lo, (
        f"holm_lo ({ci.holm_lo:.3f}) must be ≤ nominal lo ({ci.lo:.3f})"
    )
    assert ci.holm_hi >= ci.hi, (
        f"holm_hi ({ci.holm_hi:.3f}) must be ≥ nominal hi ({ci.hi:.3f})"
    )
