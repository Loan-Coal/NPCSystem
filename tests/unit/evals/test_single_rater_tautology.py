"""
Module: test_single_rater_tautology
Layer: test (unit)
Purpose: RED anchor for the κ=1.000 tautology — the secondary calibration
         axis (pre_label vs human_verdict) reports perfect agreement when
         pre_label was recorded by the same human who adjudicated, which is
         a variable compared with itself, not two independent raters. The
         real committed labels_v1.jsonl exhibits exactly this: 393 of 393
         rows carry pre_labeller_model="human-lohann" and pre_label ==
         human_verdict on every one. calibration.py must detect this and
         print "N/A (single rater)" instead of the tautological 1.000
         (EVAL-P22.3's own validation clause).
Dependencies: pytest; calibration_records, calibration (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from calibration_records import CalibrationLabel
from calibration import _print_scorer_report, calibrate_scorer, is_single_rater


def _label(
    i: int,
    *,
    pre_label: bool,
    human_verdict: bool,
    pre_labeller_model: str,
    scorer: str = "tone_judge",
) -> CalibrationLabel:
    return CalibrationLabel(
        record_id=f"case_{i:03d}:{scorer}:0",
        scorer=scorer,
        output_text=f"Output for row {i}.",
        scorer_verdict=pre_label,
        pre_label=pre_label,
        pre_labeller_model=pre_labeller_model,
        human_verdict=human_verdict,
        adjudicated_at="2026-08-07T10:00:00+00:00",
        notes="",
    )


def _self_copied_rows(n: int, scorer: str = "tone_judge") -> list[CalibrationLabel]:
    """n rows where pre_label was literally copied from human_verdict by the same human."""
    return [
        _label(i, pre_label=(i % 2 == 0), human_verdict=(i % 2 == 0),
               pre_labeller_model="human-lohann", scorer=scorer)
        for i in range(n)
    ]


def _independent_rater_rows(n: int, scorer: str = "tone_judge") -> list[CalibrationLabel]:
    """n rows with a genuine independent model rater, also perfect agreement."""
    return [
        _label(i, pre_label=(i % 2 == 0), human_verdict=(i % 2 == 0),
               pre_labeller_model="claude-opus-5", scorer=scorer)
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_self_copied_labels_print_na_not_1000() -> None:
    """The exact failure mode measured in labels_v1.jsonl: a human-prefixed
    pre_labeller_model with perfect agreement must render N/A, never a
    numeric κ or agreement value."""
    rows = _self_copied_rows(6)
    report = calibrate_scorer("tone_judge", rows)
    assert report.pre_label_is_single_rater is True

    lines: list[str] = []
    _print_scorer_report(report, print_fn=lines.append)
    text = "\n".join(lines)
    assert "N/A (single rater)" in text
    assert "Secondary κ : 1.000" not in text
    assert "Pre-label agreement : 1.000" not in text


# ---------------------------------------------------------------------------
# Behaviour: a genuine independent rater is NOT suppressed
# ---------------------------------------------------------------------------


def test_independent_model_rater_still_reports_a_real_number() -> None:
    """A genuine independent rater (e.g. Opus) must not be caught by the
    single-rater guard just because it happens to agree perfectly — the
    detection is about labeller identity, not about the agreement rate."""
    rows = _independent_rater_rows(6)
    report = calibrate_scorer("tone_judge", rows)
    assert report.pre_label_is_single_rater is False

    lines: list[str] = []
    _print_scorer_report(report, print_fn=lines.append)
    text = "\n".join(lines)
    assert "N/A (single rater)" not in text
    assert "Secondary κ : 1.000" in text


def test_is_single_rater_true_only_when_every_eligible_row_is_human() -> None:
    """A mix of one independent-rater row among human-copied rows means the
    axis is not purely self-comparison — is_single_rater must be False."""
    rows = _self_copied_rows(5) + [
        _label(99, pre_label=True, human_verdict=True, pre_labeller_model="claude-opus-5")
    ]
    assert is_single_rater(rows) is False


def test_is_single_rater_false_with_no_eligible_rows() -> None:
    """Zero eligible rows is a different failure (pre_label_kappa's own
    ValueError) — is_single_rater must not also claim True for it."""
    assert is_single_rater([]) is False


# ---------------------------------------------------------------------------
# Regression: the real committed corpus
# ---------------------------------------------------------------------------


def test_real_labels_file_is_detected_as_single_rater() -> None:
    """The actual 393-row artifact this fix exists for: every scorer must be
    flagged single-rater, so `make eval-calibrate` never publishes the
    tautological 1.000 for it.

    Filtered to gen_id="k3_73e6c36" — the original 393-row artifact this test
    names. The shared labels_v1.jsonl now also carries 354 k3_61b01dad_negadv
    rows (merged 2026-09-05, Opus-pre-labelled — a genuinely independent
    pre_labeller_model, not the human-* tautology), none yet adjudicated, so
    they are correctly absent from is_single_rater's eligible set and must not
    be folded into this specific historical assertion."""
    from pathlib import Path

    from calibration_records import read_calibration_labels

    repo_root = Path(__file__).resolve().parents[3]
    labels_path = repo_root / "evals" / "calibration" / "labels_v1.jsonl"
    if not labels_path.exists():
        import pytest

        pytest.skip("real committed artifact not present in this checkout")

    rows = [r for r in read_calibration_labels(labels_path) if r.gen_id == "k3_73e6c36"]
    scorers = sorted({r.scorer for r in rows})
    assert scorers, "expected at least one scorer in the real labels file"
    for scorer in scorers:
        scorer_rows = [r for r in rows if r.scorer == scorer]
        assert is_single_rater(scorer_rows) is True, (
            f"{scorer}: expected single-rater (all pre_labeller_model=human-*) "
            "given the measured 393-of-393 pre_label==human_verdict tautology"
        )
