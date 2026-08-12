"""
Module: tests.unit.scripts.test_check_conservation
Layer: tests
Purpose: Unit tests for scripts/check_conservation.py — pins the exact violation counts
         for the committed k3_73e6c36 artifact and proves the detector goes green on a
         synthetic fixed fixture (a detector that only ever reports failure is broken).
Dependencies: json, pathlib, sys, pytest, check_conservation
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_conservation import (  # noqa: E402
    ConservationReport,
    check_conservation,
    format_report,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GEN_DIR = _REPO_ROOT / "evals" / "generations" / "k3_73e6c36"

# ---------------------------------------------------------------------------
# Helpers for synthetic fixtures
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _make_fixed_fixture(tmp_path: Path) -> Path:
    """Create a synthetic generation directory where all 3 identities are satisfied.

    Three cases: 2 guard (case_adv_x, case_neg_y) + 1 capability (case_pos_z).
    All record_ids appear in judged.jsonl; deterministic_judged.jsonl is empty.
    All capability cases appear in judged.jsonl.

    Identity 1: guard(2) + capability(1) + excluded(0) == total(3)  → OK
    Identity 2: compare reads 3 of 3 unique record_ids               → OK
    Identity 3: cap_in_judged(1) == cap_ran(1)                       → OK
    """
    gen_dir = tmp_path / "fixed_gen"
    gen_dir.mkdir()

    outputs = [
        {
            "record_id": "case_adv_x:schema:0",
            "npc_response": "hello",
            "repetition": 0,
            "duration_ms": 50,
            "retrieved_context": ["ctx"],
            "judge_kind": None,
            "matcher_kind": "schema",
        },
        {
            "record_id": "case_neg_y:schema:0",
            "npc_response": "world",
            "repetition": 0,
            "duration_ms": 50,
            "retrieved_context": ["ctx"],
            "judge_kind": None,
            "matcher_kind": "schema",
        },
        {
            "record_id": "case_pos_z:schema:0",
            "npc_response": "ok",
            "repetition": 0,
            "duration_ms": 50,
            "retrieved_context": ["ctx"],
            "judge_kind": None,
            "matcher_kind": "schema",
        },
    ]
    _write_jsonl(gen_dir / "outputs.jsonl", outputs)

    judged = [
        {"record_id": "case_adv_x:schema:0", "case_id": "case_adv_x", "passed": True, "repetition": 0},
        {"record_id": "case_neg_y:schema:0", "case_id": "case_neg_y", "passed": True, "repetition": 0},
        {"record_id": "case_pos_z:schema:0", "case_id": "case_pos_z", "passed": True, "repetition": 0},
    ]
    _write_jsonl(gen_dir / "judged.jsonl", judged)

    # Empty deterministic_judged
    (gen_dir / "deterministic_judged.jsonl").write_text("", encoding="utf-8")

    (gen_dir / "meta.json").write_text(
        json.dumps({"gen_id": "fixed", "k": 1}), encoding="utf-8"
    )
    return gen_dir


# ---------------------------------------------------------------------------
# RED anchor — pins exact violation counts for committed artifact
# ---------------------------------------------------------------------------


def test_residual_cases_are_reported_not_dropped() -> None:
    """Exact violation counts for the committed k3_73e6c36 artifact (pinned literals).

    If any number changes, a pipeline arithmetic bug has altered the artifact —
    this is the finding the detector exists to surface.

    Identity 1 arithmetic: 78 guard (37 original + 41 ah_demo_*) + 7 capability = 85 in battery;
                            94 total − 85 = 9 in no battery.
                            Updated by EVAL-P17.2: ah_demo_* promoted from 'neither' to guard battery.
    Identity 2 arithmetic: compare reads judged.jsonl (115 unique record_ids, 345 rows);
                            judged ∪ deterministic_judged = 307 unique (115 + 192), 921 rows;
                            307 − 115 = 192 never read (62.5%).
    Identity 3 arithmetic: only 2 of 7 capability case_ids appear in judged.jsonl;
                            the other 5 route to deterministic_judged, invisible to compare.
    """
    report = check_conservation(_GEN_DIR)

    # identity 1: 78 guard + 7 capability = 85 of 94 cases; 9 cases in no battery
    # (9 = the 6 excluded-prefix cases: case_001_*, case_002_*, case_003_*, case_voice_*,
    # moderation_*, reputation_* — counted as 'neither' by check_conservation)
    assert not report.identity_1.ok
    assert report.identity_1.guard_cases == 78  # 37 original + 41 ah_demo_* (EVAL-P17.2)
    assert report.identity_1.capability_cases == 7
    assert report.identity_1.total_cases == 94
    assert report.identity_1.neither_cases == 9  # 94 - 78 - 7

    # identity 2: compare reads 115 of 307 unique record_ids (345 of 921 rows)
    assert not report.identity_2.ok
    assert report.identity_2.compare_slots == 115
    assert report.identity_2.all_slots == 307
    assert report.identity_2.compare_rows == 345
    assert report.identity_2.all_rows == 921  # 345 + 576

    # identity 3: capability battery sees 2, while 7 capability cases ran
    assert not report.identity_3.ok
    assert report.identity_3.cap_in_judged == 2
    assert report.identity_3.cap_ran == 7


# ---------------------------------------------------------------------------
# Fixed fixture — proves the detector goes green (not just stuck on red)
# ---------------------------------------------------------------------------


def test_all_violations_cleared_on_fixed_fixture(tmp_path: Path) -> None:
    """Conservation report is all-OK on a synthetic artifact where every identity holds."""
    gen_dir = _make_fixed_fixture(tmp_path)
    report = check_conservation(gen_dir)

    assert report.identity_1.ok, f"identity 1 unexpectedly failed: {report.identity_1}"
    assert report.identity_2.ok, f"identity 2 unexpectedly failed: {report.identity_2}"
    assert report.identity_3.ok, f"identity 3 unexpectedly failed: {report.identity_3}"


# ---------------------------------------------------------------------------
# format_report — spot checks
# ---------------------------------------------------------------------------


def test_format_report_mentions_all_three_violations() -> None:
    """format_report names every failing identity for the real artifact."""
    report = check_conservation(_GEN_DIR)
    text = format_report(report)
    assert "FAIL" in text
    assert "9 cases in no battery" in text  # 94 - 78 - 7; updated by EVAL-P17.2
    assert "62.5% never read" in text
    assert "capability battery sees 2" in text


def test_format_report_all_ok_on_fixed_fixture(tmp_path: Path) -> None:
    """format_report says 'All identities satisfied' on a clean fixture."""
    gen_dir = _make_fixed_fixture(tmp_path)
    text = format_report(check_conservation(gen_dir))
    assert "All identities satisfied" in text
    assert "violation" not in text


# ---------------------------------------------------------------------------
# RED anchor — main() exit code
# ---------------------------------------------------------------------------


def test_violation_exits_nonzero() -> None:
    """main() exits non-zero when any identity fails; exits 0 on a clean fixture."""
    from check_conservation import main  # noqa: E402

    # Real artifact has violations — must exit non-zero
    exit_code = main(["--gen-dir", str(_GEN_DIR)])
    assert exit_code != 0, "expected non-zero exit when violations present"


def test_no_violation_exits_zero(tmp_path: Path) -> None:
    """main() exits 0 when all identities pass."""
    from check_conservation import main  # noqa: E402

    gen_dir = _make_fixed_fixture(tmp_path)
    exit_code = main(["--gen-dir", str(gen_dir)])
    assert exit_code == 0, "expected zero exit when all identities pass"


# ---------------------------------------------------------------------------
# ISSUE-151 regression — main() must not crash on a cp1252 console
# ---------------------------------------------------------------------------


def test_main_does_not_crash_on_cp1252_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() survives a cp1252 stdout, which the real report's '∪' glyph would break.

    Reproduces ISSUE-151: a Windows console defaults to cp1252 and `print()` on the
    unreconfigured stream raises UnicodeEncodeError on the U+222A in Identity 2's
    label, taking `make check` down with it.
    """
    from check_conservation import main  # noqa: E402

    cp1252_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", cp1252_stdout)

    main(["--gen-dir", str(_GEN_DIR)])  # must not raise UnicodeEncodeError
