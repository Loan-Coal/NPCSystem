"""
Module: test_compare
Layer: test (unit)
Purpose: Tests for evals/compare.py — compare_runs, CompareResult, format_report.
Dependencies: pytest, compare (evals/), pathlib
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from compare import compare_runs, format_report, main


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _write_judged_jsonl(gen_dir: Path, rows: list[dict]) -> None:
    """Write a minimal judged.jsonl fixture file to gen_dir."""
    gen_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row) for row in rows]
    (gen_dir / "judged.jsonl").write_text("\n".join(lines), encoding="utf-8")


def _write_det_judged_jsonl(gen_dir: Path, rows: list[dict]) -> None:
    """Write a minimal deterministic_judged.jsonl fixture file to gen_dir."""
    gen_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row) for row in rows]
    (gen_dir / "deterministic_judged.jsonl").write_text("\n".join(lines), encoding="utf-8")


def _det_row(record_id: str, passed: bool, repetition: int = 0) -> dict:
    """Return a minimal deterministic_judged.jsonl row dict."""
    return {
        "record_id": record_id,
        "repetition": repetition,
        "matcher_kind": "schema",
        "passed": passed,
        "score": passed,
        "reasoning": "",
    }


def _write_meta(
    gen_dir: Path,
    *,
    gen_id: str = "gen",
    k: int = 3,
    harness_version: str | None = "hv_abc123",
    judge_model: str | None = "mixtral:8x7b",
) -> None:
    """Write a minimal meta.json fixture with comparability config fields."""
    gen_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "gen_id": gen_id,
        "k": k,
        "config": {"harness_version": harness_version, "judge_model": judge_model},
    }
    (gen_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _row(record_id: str, passed: bool, repetition: int = 0) -> dict:
    """Return a minimal judged.jsonl row dict."""
    return {
        "record_id": record_id,
        "case_id": record_id.split(":")[0],
        "judge_kind": "tone_judge",
        "passed": passed,
        "score": passed,
        "detail": "",
        "judge_model": "mixtral:8x7b",
        "repetition": repetition,
    }


# ---------------------------------------------------------------------------
# RED anchor — missing-cases must be named, not silently dropped
# ---------------------------------------------------------------------------


def test_cases_missing_from_one_run_are_named_not_dropped(tmp_path: Path) -> None:
    """Cases present in one run but absent from the other are named, not dropped.

    before run: case_alpha (1 slot), case_shared (1 slot)
    after  run: case_beta  (1 slot), case_shared (1 slot)

    Groups by case_id, so only_in_before/after track cases — not expectation slots.
    Expected:
      intersection_size = 1 (case_shared)
      only_in_before = ('case_alpha',)
      only_in_after  = ('case_beta',)
    """
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"

    _write_judged_jsonl(before_dir, [
        _row("case_alpha:tone_judge:0", passed=True),
        _row("case_shared:tone_judge:0", passed=True),
    ])
    _write_judged_jsonl(after_dir, [
        _row("case_beta:tone_judge:0", passed=False),
        _row("case_shared:tone_judge:0", passed=True),
    ])

    result = compare_runs(before_dir, after_dir)

    assert result.intersection_size == 1
    assert "case_alpha" in result.only_in_before
    assert "case_beta" in result.only_in_after
    assert "case_shared" not in result.only_in_before
    assert "case_shared" not in result.only_in_after


# ---------------------------------------------------------------------------
# Self-comparison → no_detectable_change, p=1.0
# ---------------------------------------------------------------------------


def test_compare_run_against_itself_yields_no_detectable_change(tmp_path: Path) -> None:
    """Comparing a run against itself: p=1.0, zero discordant pairs, correct verdict."""
    gen_dir = tmp_path / "run"
    _write_judged_jsonl(gen_dir, [
        _row("case_001:tone_judge:0", passed=True),
        _row("case_002:tone_judge:0", passed=False),
        _row("case_003:tone_judge:0", passed=True),
    ])

    result = compare_runs(gen_dir, gen_dir)

    assert result.intersection_size == 3
    assert len(result.only_in_before) == 0
    assert len(result.only_in_after) == 0
    assert result.paired_result.p_value == 1.0
    assert result.paired_result.verdict == "no_detectable_change"
    assert result.paired_result.improved == 0
    assert result.paired_result.regressed == 0


# ---------------------------------------------------------------------------
# Delta table ordering — regressions first
# ---------------------------------------------------------------------------


def test_delta_table_sorted_regressions_first(tmp_path: Path) -> None:
    """The delta table is sorted: regressed → improved → unchanged."""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"

    _write_judged_jsonl(before_dir, [
        _row("case_unchanged:tone_judge:0", passed=True),
        _row("case_improved:tone_judge:0", passed=False),
        _row("case_regressed:tone_judge:0", passed=True),
    ])
    _write_judged_jsonl(after_dir, [
        _row("case_unchanged:tone_judge:0", passed=True),
        _row("case_improved:tone_judge:0", passed=True),
        _row("case_regressed:tone_judge:0", passed=False),
    ])

    result = compare_runs(before_dir, after_dir)

    changes = [d.change for d in result.case_deltas]
    assert "regressed" in changes
    assert "improved" in changes
    assert "unchanged" in changes
    # regressions come before improvements and unchanged
    reg_idx = next(i for i, c in enumerate(changes) if c == "regressed")
    imp_idx = next(i for i, c in enumerate(changes) if c == "improved")
    unc_idx = next(i for i, c in enumerate(changes) if c == "unchanged")
    assert reg_idx < imp_idx
    assert reg_idx < unc_idx


# ---------------------------------------------------------------------------
# format_report — verdict + p-value + k in output
# ---------------------------------------------------------------------------


def test_format_report_contains_verdict_p_value_and_k(tmp_path: Path) -> None:
    """format_report output contains the verdict, p-value, and k for each case."""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"

    # 8 cases improve, 1 regresses → p≈0.039 < 0.05 → 'better'
    before_rows = [_row(f"case_{i:03d}:tone_judge:0", passed=False) for i in range(8)]
    before_rows.append(_row("case_008:tone_judge:0", passed=True))
    after_rows = [_row(f"case_{i:03d}:tone_judge:0", passed=True) for i in range(8)]
    after_rows.append(_row("case_008:tone_judge:0", passed=False))

    _write_judged_jsonl(before_dir, before_rows)
    _write_judged_jsonl(after_dir, after_rows)

    result = compare_runs(before_dir, after_dir)
    lines = format_report(result)
    report = "\n".join(lines)

    assert "better" in report.lower()
    assert "p=" in report.lower() or "p =" in report.lower()
    # k is printed in the delta table rows (e.g. '0/1' or '1/1')
    assert "/1" in report


# ---------------------------------------------------------------------------
# Empty judged.jsonl → trivial CompareResult
# ---------------------------------------------------------------------------


def test_empty_runs_produce_empty_intersection(tmp_path: Path) -> None:
    """Two runs with no judged rows: intersection=0, no missing cases, p=1.0."""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    _write_judged_jsonl(before_dir, [])
    _write_judged_jsonl(after_dir, [])

    result = compare_runs(before_dir, after_dir)

    assert result.intersection_size == 0
    assert len(result.only_in_before) == 0
    assert len(result.only_in_after) == 0
    assert result.paired_result.p_value == 1.0
    assert result.paired_result.verdict == "no_detectable_change"


# ---------------------------------------------------------------------------
# Evasion regression rule — capability down, guard up
# ---------------------------------------------------------------------------


def test_capability_down_guard_up_is_called_evasion(tmp_path: Path) -> None:
    """6 capability cases regress, 4 guard cases improve → regression_evasion.

    Even though 4 new guard passes could read as progress, capability regressions
    reveal the model bought guard headroom by degrading useful behaviour.  The
    paired evasion detector must fire and override the raw verdict.

    before: 6 capability pass, 0 guard pass
    after:  0 capability pass, 4 guard pass
    Total passes: before=6, after=4 — a net drop, but any mixed reading of
    guard+capability together hides the capability loss.
    """
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"

    cap_before = [_row(f"case_pos_{i:03d}:tone_judge:0", passed=True) for i in range(6)]
    cap_after = [_row(f"case_pos_{i:03d}:tone_judge:0", passed=False) for i in range(6)]

    guard_before = [_row(f"case_adv_{i:03d}:tone_judge:0", passed=False) for i in range(4)]
    guard_after = [_row(f"case_adv_{i:03d}:tone_judge:0", passed=True) for i in range(4)]

    _write_judged_jsonl(before_dir, cap_before + guard_before)
    _write_judged_jsonl(after_dir, cap_after + guard_after)

    result = compare_runs(before_dir, after_dir)

    assert result.paired_result.verdict == "regression_evasion"


# ---------------------------------------------------------------------------
# Per-source slot counts in header (EVAL-P17.1)
# ---------------------------------------------------------------------------


def test_per_source_counts_in_compare_result_and_report(tmp_path: Path) -> None:
    """CompareResult carries per-source slot counts; format_report prints them in header.

    before: 1 judged slot + 2 deterministic slots
    after:  1 judged slot + 2 deterministic slots
    """
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"

    _write_judged_jsonl(before_dir, [_row("case_001:tone_judge:0", passed=True)])
    _write_det_judged_jsonl(before_dir, [
        _det_row("case_001:schema:0", passed=True),
        _det_row("case_002:schema:0", passed=False),
    ])
    _write_judged_jsonl(after_dir, [_row("case_001:tone_judge:0", passed=True)])
    _write_det_judged_jsonl(after_dir, [
        _det_row("case_001:schema:0", passed=True),
        _det_row("case_002:schema:0", passed=True),
    ])

    result = compare_runs(before_dir, after_dir)

    assert result.before_judged_slots == 1
    assert result.before_det_slots == 2
    assert result.after_judged_slots == 1
    assert result.after_det_slots == 2

    lines = format_report(result)
    header = "\n".join(lines[:6])
    assert "judged" in header
    assert "deterministic" in header
    assert "1" in header   # judged slot count
    assert "2" in header   # deterministic slot count


# ---------------------------------------------------------------------------
# Comparability refusal (EVAL-P18.3)
# ---------------------------------------------------------------------------


def test_empty_intersection_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Two runs sharing zero case_ids: main() exits non-zero, not a confident verdict."""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    _write_judged_jsonl(before_dir, [_row("case_alpha:tone_judge:0", passed=True)])
    _write_meta(before_dir)
    _write_judged_jsonl(after_dir, [_row("case_beta:tone_judge:0", passed=True)])
    _write_meta(after_dir)

    exit_code = main(["--before", str(before_dir), "--after", str(after_dir)])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "empty intersection" in (captured.out + captured.err).lower()


def test_harness_version_mismatch_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Same cases, different harness_version: refuse rather than report a verdict."""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    _write_judged_jsonl(before_dir, [_row("case_shared:tone_judge:0", passed=True)])
    _write_meta(before_dir, harness_version="hv_before")
    _write_judged_jsonl(after_dir, [_row("case_shared:tone_judge:0", passed=True)])
    _write_meta(after_dir, harness_version="hv_after")

    exit_code = main(["--before", str(before_dir), "--after", str(after_dir)])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "harness_version" in (captured.out + captured.err).lower()


def test_judge_model_or_k_mismatch_exits_nonzero(tmp_path: Path) -> None:
    """Same cases and harness_version, different k: refuse via the comparability check."""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    _write_judged_jsonl(before_dir, [_row("case_shared:tone_judge:0", passed=True)])
    _write_meta(before_dir, k=3)
    _write_judged_jsonl(after_dir, [_row("case_shared:tone_judge:0", passed=True)])
    _write_meta(after_dir, k=1)

    result = compare_runs(before_dir, after_dir)

    assert result.refusal_reason is not None
    assert "k" in result.refusal_reason.lower()


def test_matching_meta_and_nonempty_intersection_is_comparable(tmp_path: Path) -> None:
    """Same harness_version, judge_model, and k: main() exits 0, no refusal."""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    _write_judged_jsonl(before_dir, [_row("case_shared:tone_judge:0", passed=True)])
    _write_meta(before_dir)
    _write_judged_jsonl(after_dir, [_row("case_shared:tone_judge:0", passed=True)])
    _write_meta(after_dir)

    exit_code = main(["--before", str(before_dir), "--after", str(after_dir)])

    assert exit_code == 0


def test_self_comparison_without_meta_json_still_succeeds(tmp_path: Path) -> None:
    """Two runs missing meta.json entirely are still comparable to each other (both None == None)."""
    gen_dir = tmp_path / "run"
    _write_judged_jsonl(gen_dir, [_row("case_001:tone_judge:0", passed=True)])

    result = compare_runs(gen_dir, gen_dir)

    assert result.refusal_reason is None
