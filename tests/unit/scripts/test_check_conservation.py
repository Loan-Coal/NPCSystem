"""
Module: tests.unit.scripts.test_check_conservation
Layer: tests
Purpose: Unit tests for scripts/check_conservation.py — pins the exact counts for the
         committed k3_73e6c36 artifact and proves the detector goes green on a synthetic
         fixed fixture (a detector that only ever reports failure is broken).

R1.3 (2026-08-28): Identity 2 (all_slots == compare_slots) was a tautology and removed.
Tests updated accordingly. Identities 1 and 3 remain.
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
    """Create a synthetic generation directory where identities 1 and 3 are satisfied.

    Three cases: 2 guard (case_adv_x, case_neg_y) + 1 capability (case_pos_z).
    All record_ids appear in judged.jsonl; deterministic_judged.jsonl is empty.

    Identity 1: guard(2) + capability(1) + excluded(0) == total(3)  → OK
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


def _make_broken_fixture(tmp_path: Path) -> Path:
    """Create a synthetic generation directory with a genuine Identity 3 violation.

    Same as _make_fixed_fixture, but case_pos_z ran (present in outputs.jsonl)
    and has no verdict row in either judged.jsonl or deterministic_judged.jsonl
    — a capability case that was never actually scored.
    """
    gen_dir = tmp_path / "broken_gen"
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
        # case_pos_z: no row here and none in deterministic_judged either.
    ]
    _write_jsonl(gen_dir / "judged.jsonl", judged)
    (gen_dir / "deterministic_judged.jsonl").write_text("", encoding="utf-8")
    (gen_dir / "meta.json").write_text(
        json.dumps({"gen_id": "broken", "k": 1}), encoding="utf-8"
    )
    return gen_dir


# ---------------------------------------------------------------------------
# Identities 1 and 3 hold against the committed artifact (ISSUE-172)
# ---------------------------------------------------------------------------


def test_all_identities_hold_against_the_committed_artifact() -> None:
    """Exact counts for the committed k3_73e6c36 artifact (pinned literals).

    If any number changes, a pipeline arithmetic bug has altered the artifact.

    Identity 1 arithmetic: 78 guard + 7 capability + 9 excluded (case_001-003,
                            case_voice_*, moderation_everyone_*,
                            reputation_dialogue_tone_001 — legitimately excluded
                            by classify_battery, not uncategorized) == 94 total.
    Identity 3 arithmetic: all 7 capability case_ids appear in the unified rows
                            (2 via judged.jsonl, 5 via deterministic_judged.jsonl).
    """
    report = check_conservation(_GEN_DIR)

    assert report.identity_1.ok, f"identity 1 unexpectedly failed: {report.identity_1}"
    assert report.identity_1.guard_cases == 78
    assert report.identity_1.capability_cases == 7
    assert report.identity_1.explicitly_excluded_cases == 9
    assert report.identity_1.total_cases == 94

    assert report.identity_3.ok, f"identity 3 unexpectedly failed: {report.identity_3}"
    assert report.identity_3.cap_in_judged == 7
    assert report.identity_3.cap_ran == 7


# ---------------------------------------------------------------------------
# Fixed fixture — proves the detector goes green (not just stuck on red)
# ---------------------------------------------------------------------------


def test_all_violations_cleared_on_fixed_fixture(tmp_path: Path) -> None:
    """Conservation report is all-OK on a synthetic artifact where both identities hold."""
    gen_dir = _make_fixed_fixture(tmp_path)
    report = check_conservation(gen_dir)

    assert report.identity_1.ok, f"identity 1 unexpectedly failed: {report.identity_1}"
    assert report.identity_3.ok, f"identity 3 unexpectedly failed: {report.identity_3}"


# ---------------------------------------------------------------------------
# format_report — spot checks
# ---------------------------------------------------------------------------


def test_format_report_says_all_satisfied_for_the_real_artifact() -> None:
    """format_report reports all identities OK for the real k3_73e6c36 artifact.

    Superseded test_format_report_mentions_all_three_violations, which pinned
    the pre-ISSUE-172-fix script bugs as expected FAIL output.
    """
    report = check_conservation(_GEN_DIR)
    text = format_report(report)
    assert "FAIL" not in text
    assert "All identities satisfied" in text


def test_format_report_all_ok_on_fixed_fixture(tmp_path: Path) -> None:
    """format_report says 'All identities satisfied' on a clean fixture."""
    gen_dir = _make_fixed_fixture(tmp_path)
    text = format_report(check_conservation(gen_dir))
    assert "All identities satisfied" in text
    assert "violation" not in text


# ---------------------------------------------------------------------------
# RED anchor — main() exit code
# ---------------------------------------------------------------------------


def test_violation_exits_nonzero(tmp_path: Path) -> None:
    """main() exits non-zero when any identity fails; exits 0 on a clean fixture.

    Uses a synthetic broken fixture rather than the real k3_73e6c36 artifact —
    the real artifact no longer has a violation to detect (ISSUE-172 fix); this
    test instead proves the detector still catches a genuine one.
    """
    from check_conservation import main  # noqa: E402

    gen_dir = _make_broken_fixture(tmp_path)
    exit_code = main(["--gen-dir", str(gen_dir)])
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
    """main() survives a cp1252 stdout — belt-and-suspenders guard from ISSUE-151."""
    from check_conservation import main  # noqa: E402

    cp1252_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", cp1252_stdout)

    main(["--gen-dir", str(_GEN_DIR)])  # must not raise UnicodeEncodeError
