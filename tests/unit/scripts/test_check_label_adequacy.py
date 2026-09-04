"""
Module: tests.unit.scripts.test_check_label_adequacy
Layer: tests
Purpose: Enforcement for scripts/check_label_adequacy.py — the per-scorer label
         adequacy report (DEC-260). Not wired into `make check` (DEC-224/DEC-250,
         same shape as check-readme-paths, R4.6); this test is what runs instead,
         via test-cov-evals inside `make check`.
Dependencies: pathlib, pytest; scripts.check_label_adequacy, calibration_records (evals/)
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from calibration_records import CalibrationLabel, write_calibration_labels  # noqa: E402
from scripts.check_label_adequacy import main  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_LABELS = _REPO_ROOT / "evals" / "calibration" / "labels_v1.jsonl"


def _label(i: int, *, human_verdict: bool, case_id: str) -> CalibrationLabel:
    """One minimal adjudicated CalibrationLabel row, scored by tone_judge."""
    return CalibrationLabel(
        record_id=f"{case_id}:tone_judge:0",
        scorer="tone_judge",
        output_text=f"output {i}",
        scorer_verdict=True,
        pre_label=True,
        pre_labeller_model="claude-opus-5",
        human_verdict=human_verdict,
        adjudicated_at="2026-09-01T00:00:00Z",
        notes="",
    )


def test_the_real_corpus_is_refused_end_to_end() -> None:
    """RED anchor: main() must reach the same verdict as label_adequacy directly —
    every scorer in the real committed corpus is refused, so this exits 1."""
    if not _REAL_LABELS.exists():
        import pytest

        pytest.skip("real committed labels not present in this checkout")
    assert main(["--labels", str(_REAL_LABELS)]) == 1


def test_the_counterfactual_an_adequate_corpus_exits_zero(tmp_path: Path, capsys) -> None:
    """The gate can actually pass: a labels file clearing both floors for its one
    scorer exits 0 and reports OK."""
    path = tmp_path / "labels.jsonl"
    majority = [_label(i, human_verdict=True, case_id=f"maj_{i:03d}") for i in range(40)]
    minority = [_label(100 + i, human_verdict=False, case_id=f"min_{i:03d}") for i in range(30)]
    write_calibration_labels(path, majority + minority)

    exit_code = main(["--labels", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "OK" in out
    assert "REFUSED" not in out


def test_a_refused_scorer_names_itself_and_the_counts(tmp_path: Path, capsys) -> None:
    """The report must name which scorer failed and why, not just fail silently."""
    path = tmp_path / "labels.jsonl"
    majority = [_label(i, human_verdict=True, case_id=f"maj_{i:03d}") for i in range(5)]
    minority = [_label(100 + i, human_verdict=False, case_id=f"min_{i:03d}") for i in range(2)]
    write_calibration_labels(path, majority + minority)

    exit_code = main(["--labels", str(path)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "REFUSED" in out
    assert "tone_judge" in out
    assert "2" in out
