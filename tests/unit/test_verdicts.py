"""
test_verdicts.py - Unit tests for evals/verdicts.py.

Covers:
- write_verdicts persists one entry per case, keyed by case_id
- a case whose every expectation is skipped is marked skipped=True
- totals separate evaluated_cases from raw pass counts (the 41/53 trap)
- expectation records keep kind/passed/skipped/detail
- the output is deterministic (same results -> byte-identical file)
- duplicate case_ids raise rather than silently collapsing
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# evals/ is on pytest pythonpath (pyproject.toml pythonpath = [..., "evals"])
from verdicts import DuplicateCaseIdError, write_verdicts


def _case(case_id: str, *, passed: bool, skipped: bool = False) -> dict:
    """Build a runner-shaped result dict for one case."""
    return {
        "case_id": case_id,
        "description": f"desc {case_id}",
        "passed": passed,
        "expectations": [
            {
                "kind": "runner" if skipped else "keyword_none",
                "passed": passed,
                "skipped": skipped,
                "detail": "SKIP: NPC not found" if skipped else "",
            }
        ],
    }


def test_write_verdicts_keys_every_case(tmp_path: Path) -> None:
    results = [_case("case_a", passed=True), _case("case_b", passed=False)]
    path = write_verdicts(results, tmp_path / "verdicts.json", source="runner")

    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data["cases"]) == {"case_a", "case_b"}
    assert data["cases"]["case_b"]["passed"] is False
    assert data["source"] == "runner"


def test_skipped_case_is_marked_skipped(tmp_path: Path) -> None:
    results = [_case("case_skip", passed=True, skipped=True)]
    path = write_verdicts(results, tmp_path / "verdicts.json", source="runner")

    entry = json.loads(path.read_text(encoding="utf-8"))["cases"]["case_skip"]
    assert entry["skipped"] is True
    # The runner reports skipped cases as passed=True; the raw flag is preserved
    # verbatim so the evaluated-only count can be recomputed later.
    assert entry["passed"] is True


def test_totals_exclude_skipped_from_evaluated(tmp_path: Path) -> None:
    results = [
        _case("case_pass", passed=True),
        _case("case_fail", passed=False),
        _case("case_skip", passed=True, skipped=True),
    ]
    path = write_verdicts(results, tmp_path / "verdicts.json", source="runner")

    totals = json.loads(path.read_text(encoding="utf-8"))["totals"]
    assert totals["total_cases"] == 3
    assert totals["skipped_cases"] == 1
    assert totals["evaluated_cases"] == 2
    # Raw passed counts skipped-as-passed (2); evaluated passed does not (1).
    assert totals["passed_cases_raw"] == 2
    assert totals["passed_evaluated"] == 1


def test_expectations_are_preserved(tmp_path: Path) -> None:
    path = write_verdicts(
        [_case("case_a", passed=False)], tmp_path / "verdicts.json", source="runner"
    )

    exps = json.loads(path.read_text(encoding="utf-8"))["cases"]["case_a"]["expectations"]
    assert exps == [
        {"kind": "keyword_none", "passed": False, "skipped": False, "detail": ""}
    ]


def test_output_is_deterministic(tmp_path: Path) -> None:
    results = [_case("case_b", passed=True), _case("case_a", passed=False)]
    first = write_verdicts(results, tmp_path / "one.json", source="runner").read_bytes()
    second = write_verdicts(results, tmp_path / "two.json", source="runner").read_bytes()

    assert first == second


def test_duplicate_case_id_raises(tmp_path: Path) -> None:
    results = [_case("case_a", passed=True), _case("case_a", passed=False)]

    with pytest.raises(DuplicateCaseIdError):
        write_verdicts(results, tmp_path / "verdicts.json", source="runner")
