"""
Module: test_runner_skips
Layer: test (unit)
Purpose: Verify that skipped cases (no input, NPC 404) are not counted as passes
         in report.py — neither in the numerator nor the denominator of the top line.
Dependencies: report (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

from report import write_report


def _skipped_result(case_id: str, skip_detail: str) -> dict:
    """Build a minimal skipped case result dict matching the post-fix runner shape."""
    return {
        "case_id": case_id,
        "description": "NPC from unseeded world",
        "passed": True,
        "skipped": True,
        "skip_detail": skip_detail,
        "expectations": [
            {
                "kind": "runner",
                "passed": True,
                "skipped": True,
                "detail": skip_detail,
            }
        ],
        "response": None,
        "error": None,
    }


def _non_skipped_result(case_id: str, *, passed: bool) -> dict:
    """Build a minimal non-skipped case result dict."""
    return {
        "case_id": case_id,
        "description": "",
        "passed": passed,
        "skipped": False,
        "expectations": [
            {"kind": "keyword_none", "passed": passed, "skipped": False, "detail": ""}
        ],
        "response": {"npc_response": "some response"},
        "error": None,
    }


def test_skipped_case_is_not_counted_as_passed(tmp_path: Path) -> None:
    """A skipped case must not appear in passed/total (neither numerator nor denominator).

    The top-line header must read '0/0 cases passed, 1 skipped', not '1/1 cases passed'.
    """
    result = _skipped_result(
        "case_adv_vw_guard_01",
        "SKIP: NPC 'vw_guard_01' not found. Run: make seed-village-world",
    )
    report_path = write_report(results=[result], output_dir=tmp_path)
    content = report_path.read_text(encoding="utf-8")
    assert "0/0 cases passed" in content, (
        f"skipped case counted in passed/total (top line shows skip as pass); "
        f"got:\n{content[:600]}"
    )
    assert "1/1 cases passed" not in content, (
        f"skip inflating pass count in top line; got:\n{content[:600]}"
    )


def test_skip_detail_appears_in_report(tmp_path: Path) -> None:
    """The skip_detail message must appear in the per-case section of the report."""
    detail = "SKIP: NPC 'vw_guard_01' not found. Run: make seed-village-world"
    result = _skipped_result("case_adv_vw_guard_01", detail)
    report_path = write_report(results=[result], output_dir=tmp_path)
    content = report_path.read_text(encoding="utf-8")
    assert "vw_guard_01" in content, f"skip_detail not surfaced in report; got:\n{content[:600]}"


def test_mixed_skipped_and_passed(tmp_path: Path) -> None:
    """Passed and skipped cases are reported as X/Y passed, Z skipped (Y excludes skips).

    The top-line header must read '2/2 cases passed, 1 skipped', not '3/3 cases passed'.
    """
    guard = _non_skipped_result("case_adv_false_premise", passed=True)
    cap = _non_skipped_result("case_pos_basic_dialogue", passed=True)
    skipped = _skipped_result(
        "case_adv_vw_guard_01",
        "SKIP: NPC 'vw_guard_01' not found. Run: make seed-village-world",
    )
    report_path = write_report(results=[guard, cap, skipped], output_dir=tmp_path)
    content = report_path.read_text(encoding="utf-8")
    assert "2/2 cases passed" in content, (
        f"skip inflated total (expected 2/2, skip excluded); got:\n{content[:600]}"
    )
    assert "1 skipped" in content, f"skip count missing from top line; got:\n{content[:600]}"
    assert "3/3 cases passed" not in content, (
        f"skip counted in denominator; got:\n{content[:600]}"
    )
