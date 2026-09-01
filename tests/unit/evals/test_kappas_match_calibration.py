"""
Module: test_kappas_match_calibration
Layer: tests (unit)
Purpose: RED anchor for ISSUE-244 — mde.RECORDED_KAPPAS must equal the calibration
         record, which is the authoritative kappa family. Three rival families
         circulated: calibration (0.849/0.530/0.247), mde.py's recorded
         (1.000/0.282/0.225), and the panel Fleiss per-criterion (0.753/0.519/0.422).
Dependencies: pytest; mde (evals/)
Used by: `make test`, `make check` via test-cov-evals.
"""

from __future__ import annotations

import json
from pathlib import Path

from mde import RECORDED_KAPPAS

REPO_ROOT = Path(__file__).resolve().parents[3]
_TREND_ROW = REPO_ROOT / "evals" / "trend" / "trend_v1.jsonl"


def _calibration_kappas() -> dict[str, float]:
    """Read the calibration kappa per scorer from the committed trend row."""
    row = json.loads(_TREND_ROW.read_text(encoding="utf-8").splitlines()[0])
    return {s["scorer"]: s["kappa"] for s in row["scorer_kappas"]}


def test_recorded_kappas_equal_the_calibration_record() -> None:
    """RED anchor. Measured 2026-09-01: 1.000 vs 0.849, 0.282 vs 0.530, 0.225 vs 0.247."""
    calibration = _calibration_kappas()
    for name, kappa in RECORDED_KAPPAS:
        assert name in calibration, f"{name} has no calibration record"
        assert round(kappa, 3) == round(calibration[name], 3), (
            f"{name}: mde.py records {kappa}, calibration measured {calibration[name]}"
        )


def test_every_recorded_kappa_is_a_real_measurement() -> None:
    """A kappa of exactly 1.000 is the tell of an unanimous panel, not a reliability.

    ISSUE-244: mde.py carried tone_judge at 1.000 because the panel agreed 135/135.
    Calibration against human labels puts it at 0.849. An exactly-1.000 kappa makes
    `true_mde_pp = observed_pp / kappa` a no-op, silently claiming the judge adds no noise.
    """
    for name, kappa in RECORDED_KAPPAS:
        assert 0.0 < kappa < 1.0, f"{name} kappa {kappa} is degenerate"
