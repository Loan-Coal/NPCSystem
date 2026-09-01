"""
Module: test_aggregator_join
Layer: tests (unit)
Purpose: RED anchor + behaviour tests for the verdict-source join (R2.6b / CR-L03-06).
         `load_unified_rows` deduplicated by `record_id` alone, but a record_id is
         `<case_id>:<kind>:<index>` and encodes no repetition, so every k-repetition of a
         slot collapsed to the last one written. That turned turn counts into case counts.
Dependencies: pytest; verdict_sources, summary (evals/)
Used by: `make test`, `make check` via test-cov-evals.
"""

from __future__ import annotations

import json
from pathlib import Path

from summary import summarize_from_dir
from verdict_sources import DET_JUDGED_FILE, JUDGED_FILE, load_unified_rows, to_summarize_results

REPO_ROOT = Path(__file__).resolve().parents[3]
# The committed generation the published guard rate was taken from (k=3).
_GEN_DIR = REPO_ROOT / "evals" / "generations" / "k3_77688e7_regen1"


def _raw_row_count(gen_dir: Path) -> int:
    """Count non-blank lines across both verdict files, before any deduplication."""
    total = 0
    for name in (JUDGED_FILE, DET_JUDGED_FILE):
        path = gen_dir / name
        if path.exists():
            total += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return total


def _write_rows(gen_dir: Path, name: str, rows: list[dict]) -> None:
    """Write rows as jsonl into gen_dir/name."""
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / name).write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Deduplication semantics
# ---------------------------------------------------------------------------


def test_repetitions_of_one_slot_all_survive(tmp_path: Path) -> None:
    """Three repetitions of one expectation slot are three rows, not one."""
    _write_rows(
        tmp_path,
        JUDGED_FILE,
        [
            {"record_id": "case_adv_a:tone_judge:0", "case_id": "case_adv_a",
             "judge_kind": "tone_judge", "passed": True, "repetition": rep}
            for rep in (0, 1, 2)
        ],
    )
    rows = load_unified_rows(tmp_path)
    assert len(rows) == 3
    assert sorted(r.repetition for r in rows) == [0, 1, 2]


def test_judged_still_wins_over_deterministic_for_the_same_slot(tmp_path: Path) -> None:
    """Precedence is per (record_id, repetition), and judged remains authoritative."""
    _write_rows(tmp_path, DET_JUDGED_FILE, [
        {"record_id": "case_pos_a:min_length:0", "matcher_kind": "min_length",
         "passed": False, "repetition": 1}])
    _write_rows(tmp_path, JUDGED_FILE, [
        {"record_id": "case_pos_a:min_length:0", "case_id": "case_pos_a",
         "judge_kind": "min_length", "passed": True, "repetition": 1}])
    rows = load_unified_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0].source == "judged"
    assert rows[0].passed is True


def test_the_same_slot_at_different_repetitions_does_not_overwrite(tmp_path: Path) -> None:
    """A judged row must not evict a deterministic row from a different repetition."""
    _write_rows(tmp_path, DET_JUDGED_FILE, [
        {"record_id": "case_pos_a:min_length:0", "matcher_kind": "min_length",
         "passed": False, "repetition": 0}])
    _write_rows(tmp_path, JUDGED_FILE, [
        {"record_id": "case_pos_a:min_length:0", "case_id": "case_pos_a",
         "judge_kind": "min_length", "passed": True, "repetition": 1}])
    rows = load_unified_rows(tmp_path)
    assert len(rows) == 2
    assert {(r.repetition, r.source) for r in rows} == {(0, "deterministic"), (1, "judged")}


def test_turns_group_by_case_and_repetition(tmp_path: Path) -> None:
    """One (case_id, repetition) pair is one turn, however many slots it carries."""
    _write_rows(tmp_path, JUDGED_FILE, [
        {"record_id": f"case_adv_a:{kind}:0", "case_id": "case_adv_a",
         "judge_kind": kind, "passed": True, "repetition": rep}
        for rep in (0, 1) for kind in ("tone_judge", "affirms_judge")])
    results = to_summarize_results(load_unified_rows(tmp_path))
    assert len(results) == 2
    assert all(len(r["expectations"]) == 2 for r in results)


# ---------------------------------------------------------------------------
# RED anchors — the committed k=3 generation
# ---------------------------------------------------------------------------


def test_deduplication_discards_no_rows() -> None:
    """RED anchor: 975 raw rows must survive the join. Measured 2026-09-01: 325 did."""
    assert len(load_unified_rows(_GEN_DIR)) == _raw_row_count(_GEN_DIR)


def test_guard_turns_exceed_guard_cases_at_k_greater_than_one() -> None:
    """RED anchor: at k=3 a turn count cannot equal a case count.

    Measured 2026-09-01: guard_cases == guard_turns == 78, which is only possible at k=1.
    """
    summary = summarize_from_dir(_GEN_DIR)
    assert summary.guard_turns > summary.guard_cases


def test_the_two_aggregators_agree_on_the_guard_denominator() -> None:
    """RED anchor: summarize_from_dir and a direct (case_id, repetition) count must match."""
    guard_prefixes = ("case_adv_", "case_neg_", "ah_demo_")
    rows = load_unified_rows(_GEN_DIR)
    direct = {(r.case_id, r.repetition) for r in rows if r.case_id.startswith(guard_prefixes)}
    assert summarize_from_dir(_GEN_DIR).guard_turns == len(direct)
