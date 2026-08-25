"""
Module: tests.unit.scripts.test_record_trend_and_gate
Layer: tests
Purpose: Unit tests for scripts/record_trend_and_gate.py — assembling a
         TrendRow from a completed run's artifacts (EVAL-P23.1/P23.3 glue),
         resolving the ONE baseline both the compare step and the gate use
         (DEC-191 Defect A/B), and the four-way exit contract including exit 3,
         'the instrument degraded' (Defect E).
Dependencies: json, pathlib, pytest, shutil, sys; record_trend_and_gate,
         trend_store (evals/)
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from record_trend_and_gate import build_trend_row, main  # noqa: E402
from trend_store import RateWithCI, TrendRow, append_trend_row, read_trend_rows  # noqa: E402

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


# ---------------------------------------------------------------------------
# Baseline resolution — EVAL-P23 Defect A/B
# ---------------------------------------------------------------------------


def _foreign_row(gen_id: str) -> TrendRow:
    """A row recorded under a harness_version no real run in this checkout shares."""
    return TrendRow(
        gen_id=gen_id,
        harness_version="a_different_harness_version",
        recorded_at="2026-08-01T00:00:00+00:00",
        guard=RateWithCI(rate=0.99, ci_low=0.98, ci_high=1.0, n=94),
    )


def test_main_refuses_a_baseline_from_another_harness_version(tmp_path: Path) -> None:
    """The store is not empty, but nothing in it is comparable. latest_row()
    would have returned a confident verdict against an incomparable pair —
    exactly the pair compare.py refuses."""
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    append_trend_row(_foreign_row("gen_other_harness"), store)
    exit_code = main(["--gen-id", "cand", "--gen-dir", str(_GEN_DIR), "--trend-store", str(store)])
    assert exit_code == 2
    assert len(read_trend_rows(store)) == 2  # the candidate row is still recorded


def test_main_walks_back_past_an_incomparable_row(tmp_path: Path, capsys) -> None:
    """A comparable row further back is the baseline; the newest row is not
    automatically it. The output must name the chosen gen_id and its age."""
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    append_trend_row(
        build_trend_row("comparable_baseline", _GEN_DIR, labels_path=_LABELS_PATH,
                        recorded_at="2026-08-01T00:00:00+00:00"),
        store,
    )
    append_trend_row(_foreign_row("gen_other_harness"), store)

    exit_code = main(["--gen-id", "cand", "--gen-dir", str(_GEN_DIR), "--trend-store", str(store)])
    out = capsys.readouterr().out
    assert exit_code == 0  # identical artifact -> identical numbers -> no regression
    assert "comparable_baseline" in out   # names the baseline it actually used
    assert "back" in out                  # ... and how far back it sits
    assert "skipped 1" in out             # ... and that it walked past an incomparable row


def test_print_baseline_names_the_row_the_gate_would_pick(tmp_path: Path, capsys) -> None:
    """Defect A: step 7 (compare) and step 8 (gate) must describe the same pair.
    --print-baseline is how the PowerShell harness resolves that pair once."""
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    append_trend_row(
        build_trend_row("the_baseline", _GEN_DIR, labels_path=_LABELS_PATH,
                        recorded_at="2026-08-01T00:00:00+00:00"),
        store,
    )
    exit_code = main([
        "--gen-id", "cand", "--gen-dir", str(_GEN_DIR),
        "--trend-store", str(store), "--print-baseline",
    ])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "the_baseline"  # machine-readable: the id alone
    assert len(read_trend_rows(store)) == 1  # resolving must not record anything


def test_print_baseline_prints_nothing_when_no_comparable_row_exists(tmp_path: Path, capsys) -> None:
    """An empty answer means "skip the compare step", explicitly — never a
    fabricated baseline id."""
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    exit_code = main([
        "--gen-id", "cand", "--gen-dir", str(_GEN_DIR),
        "--trend-store", str(store), "--print-baseline",
    ])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == ""


def test_explicit_baseline_gen_id_is_gated_against(tmp_path: Path, capsys) -> None:
    """An explicit baseline pins both steps to the same pair even when a newer
    comparable row exists."""
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    for gen_id, when in (("older", "2026-08-01T00:00:00+00:00"), ("newer", "2026-08-10T00:00:00+00:00")):
        append_trend_row(
            build_trend_row(gen_id, _GEN_DIR, labels_path=_LABELS_PATH, recorded_at=when), store
        )
    exit_code = main([
        "--gen-id", "cand", "--gen-dir", str(_GEN_DIR),
        "--trend-store", str(store), "--baseline-gen-id", "older",
    ])
    assert exit_code == 0
    assert "older" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Instrument degradation — EVAL-P23 Defect D/E
# ---------------------------------------------------------------------------

_COPIED_ARTIFACTS = ("outputs.jsonl", "meta.json", "judged.jsonl", "deterministic_judged.jsonl")


def _copy_gen_dir(tmp_path: Path) -> Path:
    """Copy the committed artifact so a test can vary its run_status.json."""
    dest = tmp_path / "gen_copy"
    dest.mkdir()
    for name in _COPIED_ARTIFACTS:
        shutil.copyfile(_GEN_DIR / name, dest / name)
    return dest


def _write_status(gen_dir: Path, kappa: float, ci_low: float, ci_high: float) -> None:
    """Write a panel run_status.json carrying kappa with its bootstrap interval."""
    (gen_dir / "run_status.json").write_text(
        json.dumps({
            "status": "gate_failed", "cases_passed": 329, "cases_total": 345,
            "judge_panel": ["mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b"],
            "fleiss_kappa": kappa, "raw_agreement": 0.9556,
            "kappa_ci_low": ci_low, "kappa_ci_high": ci_high, "kappa_n_items": 345,
            "kappa_by_criterion": [
                {"judge_kind": "tone_judge", "kappa": 1.0, "n_items": 135, "unanimous": 135},
                {"judge_kind": "refusal_judge", "kappa": 0.225, "n_items": 75, "unanimous": 60},
            ],
            "repeat_flips": {"records_with_flips": 12, "unanimous_flips": 4,
                             "solo_flips": 8, "n_records": 115},
        }),
        encoding="utf-8",
    )


def test_build_trend_row_reads_kappa_from_run_status(tmp_path: Path) -> None:
    """Defect D: the row must carry the chance-corrected number, not only the
    base-rate-inflated raw agreement DEC-188 demoted."""
    _require_real_artifact()
    gen_dir = _copy_gen_dir(tmp_path)
    _write_status(gen_dir, kappa=0.5256, ci_low=0.227, ci_high=0.730)

    row = build_trend_row("cand", gen_dir, labels_path=_LABELS_PATH,
                          recorded_at="2026-08-18T00:00:00+00:00")
    assert row.panel_kappa is not None
    assert row.panel_kappa.kappa == 0.5256
    assert row.panel_kappa.ci_high == 0.730
    assert {c.judge_kind for c in row.kappa_by_criterion} == {"tone_judge", "refusal_judge"}
    assert row.repeat_flips is not None
    assert row.repeat_flips.solo_flips == 8
    assert row.panel_agreement_rate == 0.9556  # kept alongside, not replaced


def test_kappa_drop_exits_three_not_one(tmp_path: Path, capsys) -> None:
    """Defect E: "my ruler got worse" must not be reported as "my engine got
    worse". Same artifact on both sides — the rates are identical, only
    agreement fell."""
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    gen_dir = _copy_gen_dir(tmp_path)

    _write_status(gen_dir, kappa=0.72, ci_low=0.60, ci_high=0.81)
    append_trend_row(
        build_trend_row("baseline_run", gen_dir, labels_path=_LABELS_PATH,
                        recorded_at="2026-08-01T00:00:00+00:00"),
        store,
    )
    _write_status(gen_dir, kappa=0.30, ci_low=0.15, ci_high=0.45)
    exit_code = main(["--gen-id", "cand", "--gen-dir", str(gen_dir), "--trend-store", str(store)])

    out = capsys.readouterr().out
    assert exit_code == 3
    assert "INSTRUMENT DEGRADED" in out
    assert "NO REGRESSION DETECTED" in out  # the engine was NOT blamed


def test_stable_kappa_still_exits_zero(tmp_path: Path, capsys) -> None:
    """A panel run whose agreement held must gate on the rates as usual."""
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    gen_dir = _copy_gen_dir(tmp_path)
    _write_status(gen_dir, kappa=0.72, ci_low=0.60, ci_high=0.81)
    append_trend_row(
        build_trend_row("baseline_run", gen_dir, labels_path=_LABELS_PATH,
                        recorded_at="2026-08-01T00:00:00+00:00"),
        store,
    )
    exit_code = main(["--gen-id", "cand", "--gen-dir", str(gen_dir), "--trend-store", str(store)])
    assert exit_code == 0
    assert "INSTRUMENT STABLE" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Judge identity on the row — DEC-197
# ---------------------------------------------------------------------------


def test_the_row_records_the_instrument_that_actually_scored_the_run(tmp_path: Path) -> None:
    """Read from run_status.json, not meta.json's configured judge_model: since
    --panel landed, one generation config can be scored either way under a
    byte-identical meta.json (DEC-190). Without this the trend gate compared a
    panel-scored baseline against a single-judge candidate and reported the
    instrument change as an engine verdict."""
    _require_real_artifact()
    gen_dir = _copy_gen_dir(tmp_path)
    _write_status(gen_dir, kappa=0.5256, ci_low=0.227, ci_high=0.730)

    row = build_trend_row("cand", gen_dir, labels_path=_LABELS_PATH,
                          recorded_at="2026-08-25T00:00:00+00:00")
    # roster sorted, so seat ORDER cannot cause a spurious refusal while a
    # changed seat still does (judge_identity.render_panel_identity)
    assert row.judge_identity == "panel:llama3.1:8b+mixtral:8x7b+qwen2.5:14b"


def test_a_single_judge_run_records_that_model_as_its_instrument(tmp_path: Path) -> None:
    _require_real_artifact()
    gen_dir = _copy_gen_dir(tmp_path)
    (gen_dir / "run_status.json").write_text(
        json.dumps({"status": "ok", "cases_passed": 1, "cases_total": 1,
                    "judge_panel": [], "judge_model": "mixtral:8x7b"}),
        encoding="utf-8",
    )
    row = build_trend_row("cand", gen_dir, labels_path=_LABELS_PATH,
                          recorded_at="2026-08-25T00:00:00+00:00")
    assert row.judge_identity == "mixtral:8x7b"


def test_a_panel_baseline_does_not_gate_a_single_judge_candidate(tmp_path: Path, capsys) -> None:
    """The end-to-end form of the compounding failure: Run-OvernightCombined step 9
    records a panel-judged baseline, step 10's harness run single-judged (the
    Makefile dropped --panel), and the gate compared them anyway. It must now refuse
    and say the judge is what differs — re-judging an arm is cheap, re-running the
    engine over a phantom regression is not."""
    _require_real_artifact()
    store = tmp_path / "trend.jsonl"
    gen_dir = _copy_gen_dir(tmp_path)

    _write_status(gen_dir, kappa=0.72, ci_low=0.60, ci_high=0.81)  # panel
    append_trend_row(
        build_trend_row("panel_baseline", gen_dir, labels_path=_LABELS_PATH,
                        recorded_at="2026-08-01T00:00:00+00:00"),
        store,
    )
    (gen_dir / "run_status.json").write_text(
        json.dumps({"status": "ok", "cases_passed": 1, "cases_total": 1,
                    "judge_panel": [], "judge_model": "mixtral:8x7b"}),
        encoding="utf-8",
    )
    exit_code = main(["--gen-id", "single_cand", "--gen-dir", str(gen_dir),
                      "--trend-store", str(store)])
    out = capsys.readouterr().out
    assert exit_code == 2
    assert "NO COMPARABLE BASELINE" in out
    assert "judge" in out.lower()
