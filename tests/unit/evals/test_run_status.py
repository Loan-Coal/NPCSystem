"""
Module: test_run_status
Layer: test (unit)
Purpose: Tests for evals/run_status.py — the machine-readable run_status.json that
         lets ops scripts tell "the quality gate was not met" apart from "the
         harness broke". RED anchor for ISSUE-182: the 2026-08-17 overnight script
         read exit code 1 (194/210 cases passed) as an infra failure and halted
         Phase 2 for nothing.
Dependencies: pytest, run_status (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

import json

from run_status import RunStatus, status_for, write_run_status


def test_gate_failed_is_distinct_from_error() -> None:
    """Some cases failing is not the harness breaking."""
    assert status_for(exit_code=0) == "ok"
    assert status_for(exit_code=1) == "gate_failed"
    assert status_for(exit_code=2) == "error"


def test_gate_failed_means_the_measurement_is_usable() -> None:
    """A gate_failed run produced valid measurements; only 'error' invalidates them."""
    assert RunStatus(status="gate_failed", cases_passed=194, cases_total=210).measurement_valid
    assert RunStatus(status="ok", cases_passed=210, cases_total=210).measurement_valid
    assert not RunStatus(status="error", cases_passed=0, cases_total=0).measurement_valid


def test_run_status_roundtrips_through_json(tmp_path) -> None:
    """The written file carries everything an ops script needs to decide next steps."""
    path = tmp_path / "run_status.json"
    status = RunStatus(
        status="gate_failed",
        cases_passed=194,
        cases_total=210,
        judge_panel=("mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b"),
        fleiss_kappa=0.5256,
        raw_agreement=0.9556,
        report_path="evals/reports/x.md",
    )
    write_run_status(status, path)

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["status"] == "gate_failed"
    assert loaded["cases_passed"] == 194
    assert loaded["judge_panel"] == ["mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b"]
    assert RunStatus(**loaded).measurement_valid


def test_provenance_is_separate_from_error(tmp_path) -> None:
    """A re-derived-but-valid run records HOW it was produced without claiming failure."""
    path = tmp_path / "run_status.json"
    write_run_status(
        RunStatus(status="gate_failed", cases_passed=329, cases_total=345,
                  provenance="re-derived from a legacy artifact"),
        path,
    )
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["error"] == ""
    assert "re-derived" in loaded["provenance"]
    assert RunStatus(**loaded).measurement_valid


def test_error_status_records_the_reason(tmp_path) -> None:
    """An error run says why, so the morning handoff does not need log archaeology."""
    path = tmp_path / "run_status.json"
    write_run_status(RunStatus(status="error", error="Transcript not found: x.jsonl"), path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["status"] == "error"
    assert "Transcript not found" in loaded["error"]
