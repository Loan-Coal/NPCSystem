"""
Module: tests.unit.scripts.test_record_trend_and_gate
Layer: tests
Purpose: Unit tests for scripts/record_trend_and_gate.py — assembling a
         TrendRow from a completed run's artifacts (EVAL-P23.1/P23.3 glue).
Dependencies: pathlib, pytest, sys; record_trend_and_gate, trend_store (evals/)
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from record_trend_and_gate import build_trend_row, main  # noqa: E402
from trend_store import append_trend_row, read_trend_rows  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GEN_DIR = _REPO_ROOT / "evals" / "generations" / "k3_73e6c36"
_LABELS_PATH = _REPO_ROOT / "evals" / "calibration" / "labels_v1.jsonl"


def _require_real_artifact() -> None:
    if not _GEN_DIR.exists() or not _LABELS_PATH.exists():
        import pytest

        pytest.skip("real committed artifacts not present in this checkout")


# ---------------------------------------------------------------------------
# build_trend_row — against the real committed artifact
# ---------------------------------------------------------------------------


def test_build_trend_row_against_real_k3_artifact() -> None:
    """Assembling a TrendRow from the real k3_73e6c36 artifact must not raise
    and must populate every axis the metrics contract requires."""
    _require_real_artifact()
    row = build_trend_row("k3_73e6c36", _GEN_DIR, labels_path=_LABELS_PATH,
                           recorded_at="2026-08-17T00:00:00+00:00")
    assert row.gen_id == "k3_73e6c36"
    assert row.guard is not None
    assert row.guard.n > 0
    assert row.capability is not None
    assert row.inconclusive_rate is not None
    assert len(row.scorer_kappas) > 0  # every scorer with >=2 adjudicated rows


def test_build_trend_row_with_no_labels_file_yields_empty_kappas(tmp_path: Path) -> None:
    """A gen_dir with no calibration labels must still produce a row — the
    rate axis is independent of calibration, and an empty kappa tuple is a
    valid (if uninformative) state, never a crash."""
    _require_real_artifact()
    row = build_trend_row(
        "k3_73e6c36_nolab", _GEN_DIR,
        labels_path=tmp_path / "does_not_exist.jsonl",
        recorded_at="2026-08-17T00:00:00+00:00",
    )
    assert row.scorer_kappas == ()
    assert row.guard is not None  # rates still computed from gen_dir alone


# ---------------------------------------------------------------------------
# main() — CLI wiring
# ---------------------------------------------------------------------------


def test_main_records_first_row_with_no_baseline(tmp_path: Path) -> None:
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    exit_code = main([
        "--gen-id", "k3_73e6c36", "--gen-dir", str(_GEN_DIR),
        "--trend-store", str(store), "--allow-no-baseline",
    ])
    assert exit_code == 0
    rows = read_trend_rows(store)
    assert len(rows) == 1


def test_main_exits_two_when_no_baseline_and_not_allowed(tmp_path: Path) -> None:
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    exit_code = main(["--gen-id", "k3_73e6c36", "--gen-dir", str(_GEN_DIR), "--trend-store", str(store)])
    assert exit_code == 2
    # the row is still recorded even though the gate couldn't run — the
    # measurement isn't lost just because there was nothing to compare it to
    assert len(read_trend_rows(store)) == 1


def test_main_gates_against_a_recorded_baseline(tmp_path: Path) -> None:
    """Recording the same artifact's numbers twice under different gen_ids
    must never regress against itself."""
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    row = build_trend_row("baseline_run", _GEN_DIR, labels_path=_LABELS_PATH,
                           recorded_at="2026-08-16T00:00:00+00:00")
    append_trend_row(row, store)

    exit_code = main(["--gen-id", "candidate_run", "--gen-dir", str(_GEN_DIR), "--trend-store", str(store)])
    assert exit_code == 0  # identical artifact -> identical numbers -> no regression
