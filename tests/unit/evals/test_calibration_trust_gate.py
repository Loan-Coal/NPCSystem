"""
Module: test_calibration_trust_gate
Layer: test (unit)
Purpose: RED anchor + behaviour tests for wiring scorer_trust_policy.check_publication
         into calibration.py's report renderer (EVAL-P24.1's wiring half —
         docs/SCORER_TRUST_POLICY.md:64 says report generators "must" call it;
         nothing did). A scorer below the publication threshold must never
         print a bare numeric kappa a reader could copy into a report.
Dependencies: pytest; calibration, calibration_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

from calibration_records import CalibrationLabel
from calibration import _print_scorer_report, calibrate_scorer


def _label(i: int, *, pre_label: bool, scorer_verdict: bool, human_verdict: bool,
           scorer: str = "refusal_judge") -> CalibrationLabel:
    return CalibrationLabel(
        record_id=f"case_{i:03d}:{scorer}:0",
        scorer=scorer,
        output_text=f"output {i}",
        scorer_verdict=scorer_verdict,
        pre_label=pre_label,
        pre_labeller_model="claude-opus-5",
        human_verdict=human_verdict,
        adjudicated_at="2026-08-01T00:00:00+00:00",
        notes="",
    )


def _chance_level_rows(n: int, scorer: str = "refusal_judge") -> list[CalibrationLabel]:
    """Rows engineered to reproduce a low (near chance-level) headline kappa:
    scorer_verdict alternates independently of human_verdict."""
    rows = []
    for i in range(n):
        sv = i % 2 == 0
        hv = (i % 3 == 0)  # deliberately out of phase with sv
        rows.append(_label(i, pre_label=sv, scorer_verdict=sv, human_verdict=hv, scorer=scorer))
    return rows


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_low_kappa_scorer_headline_is_refused_not_printed_as_a_number() -> None:
    """A scorer below the publication threshold must render REFUSED, never a
    bare numeric kappa a reader could copy into a report."""
    rows = _chance_level_rows(24)
    report = calibrate_scorer("refusal_judge", rows)
    assert report.kappa < 0.60  # sanity: this fixture really is below threshold

    lines: list[str] = []
    _print_scorer_report(report, print_fn=lines.append)
    text = "\n".join(lines)
    assert "REFUSED" in text
    assert f"Headline κ : {report.kappa:.3f} " not in text


# ---------------------------------------------------------------------------
# Behaviour: a publishable scorer is unaffected
# ---------------------------------------------------------------------------


def test_publishable_scorer_prints_the_real_number() -> None:
    """A scorer at or above the publication threshold renders its real kappa
    unchanged — the gate must not suppress legitimately publishable numbers."""
    rows = [
        _label(i, pre_label=(i % 2 == 0), scorer_verdict=(i % 2 == 0), human_verdict=(i % 2 == 0),
               scorer="tone_judge")
        for i in range(12)
    ]
    report = calibrate_scorer("tone_judge", rows)
    assert report.kappa >= 0.60  # sanity: perfect agreement fixture is publishable

    lines: list[str] = []
    _print_scorer_report(report, print_fn=lines.append)
    text = "\n".join(lines)
    assert "REFUSED" not in text
    assert f"Headline κ : {report.kappa:.3f}" in text


# ---------------------------------------------------------------------------
# Regression: the real committed corpus
# ---------------------------------------------------------------------------


def test_real_refusal_judge_kappa_is_refused_on_the_real_corpus() -> None:
    """The measured real-corpus finding this exists to protect: refusal_judge
    kappa=0.247 (well below the 0.40 HIDDEN threshold) must never render as
    a bare number a README could copy."""
    repo_root = Path(__file__).resolve().parents[3]
    labels_path = repo_root / "evals" / "calibration" / "labels_v1.jsonl"
    if not labels_path.exists():
        import pytest

        pytest.skip("real committed artifact not present in this checkout")

    from calibration_records import read_calibration_labels

    rows = read_calibration_labels(labels_path)
    report = calibrate_scorer("refusal_judge", rows)
    lines: list[str] = []
    _print_scorer_report(report, print_fn=lines.append)
    text = "\n".join(lines)
    assert "REFUSED" in text
