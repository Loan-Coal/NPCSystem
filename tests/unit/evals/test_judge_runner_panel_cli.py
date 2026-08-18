"""
Module: test_judge_runner_panel_cli
Layer: test (unit)
Purpose: End-to-end test of `judge_runner.main --panel` — the wiring itself, not the
         pieces. The unit tests for judged_persistence and panel_metrics all passed
         while main() still referenced an undefined constant, because nothing
         exercised the CLI path that assembles them. This module closes that gap:
         it asserts the three artifacts appear, the two JSONL files have the right
         row counts, and run_status.json reports a usable measurement.
Dependencies: pytest, unittest.mock; eval_records, judge_panel, judge_runner,
         matchers (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import judge_panel
import judge_runner
from eval_records import GenerationRecord, write_generation_dir
from matchers import JudgeResult

_PANEL = "mixtral:8x7b,qwen2.5:14b,llama3.1:8b"
_K = 3
_N_RECORDS = 2


def _transcript(tmp_path: Path) -> Path:
    """Write a k=3 transcript of pass_on_no records and return its outputs.jsonl."""
    records = [
        GenerationRecord(
            record_id=f"case_{i}:affirms_judge:0",
            source="anti_hallucination",
            npc_id="captain_sorn",
            player_id="player_1",
            player_message="did the war end?",
            npc_response="I am just a captain of the guard.",
            criteria="Does the NPC affirm that the war has ended?",
            judge_kind="affirms_judge",
            expected_polarity="pass_on_no",
            repetition=rep,
        )
        for i in range(_N_RECORDS)
        for rep in range(_K)
    ]
    gen_dir = tmp_path / "gen"
    write_generation_dir(gen_dir, records, gen_id="cli-test", k=_K)
    return gen_dir / "outputs.jsonl"


def _run_panel(tmp_path: Path, score: bool) -> tuple[int, Path]:
    """Run main --panel with every seat stubbed to the same score.

    Patches judge_panel._run_binary_judge, NOT _default_judge_fn: the latter is
    bound as judge_transcript_panel's default argument at def time, so replacing
    the module attribute does not intercept it and the test would silently make
    real Ollama calls. _run_binary_judge is looked up as a module global on every
    call, so it is the seam that actually holds. Keep the transport as the patch
    point for any future CLI-level test here.
    """
    transcript = _transcript(tmp_path)
    gen_dir = transcript.parent

    def stub(criteria: str, content: str, model: str | None = None) -> JudgeResult:
        return JudgeResult(score=score, error="")

    with patch.object(judge_panel, "_run_binary_judge", stub):
        code = judge_runner.main([
            "--transcript", str(transcript),
            "--reports", str(tmp_path / "reports"),
            "--json-out", str(gen_dir / "judged.jsonl"),
            "--panel", "--panel-models", _PANEL,
        ])
    return code, gen_dir


def test_panel_cli_writes_all_three_artifacts(tmp_path: Path) -> None:
    """A panel run produces consensus rows, seat rows and a run status file."""
    code, gen_dir = _run_panel(tmp_path, score=False)

    assert code == 0, "every seat said NO on pass_on_no records — all should pass"
    consensus = (gen_dir / "judged.jsonl").read_text(encoding="utf-8").strip().splitlines()
    votes = (gen_dir / "judged_panel_votes.jsonl").read_text(encoding="utf-8").strip().splitlines()

    assert len(consensus) == _N_RECORDS * _K, "one consensus row per (record, repetition)"
    assert len(votes) == _N_RECORDS * _K * 3, "one row per seat per (record, repetition)"


def test_panel_cli_applies_polarity_to_persisted_rows(tmp_path: Path) -> None:
    """pass_on_no + unanimous NO is persisted as passed=True, in both files."""
    _, gen_dir = _run_panel(tmp_path, score=False)

    consensus = [json.loads(x) for x in (gen_dir / "judged.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    votes = [json.loads(x) for x in (gen_dir / "judged_panel_votes.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]

    assert all(r["passed"] is True for r in consensus)
    assert all(r["passed"] is True for r in votes)
    assert all(r["score"] is False for r in votes)
    assert {r["repetition"] for r in votes} == set(range(_K))
    assert all(r["judge_model"] == "panel:3" for r in consensus)


def test_panel_cli_run_status_reports_a_usable_measurement(tmp_path: Path) -> None:
    """run_status.json records the roster and marks the measurement valid."""
    _, gen_dir = _run_panel(tmp_path, score=False)
    status = json.loads((gen_dir / "run_status.json").read_text(encoding="utf-8"))

    assert status["status"] == "ok"
    assert status["cases_passed"] == status["cases_total"]
    assert status["judge_panel"] == _PANEL.split(",")
    assert status["votes_path"].endswith("judged_panel_votes.jsonl")


def test_panel_cli_gate_failure_is_not_an_error(tmp_path: Path) -> None:
    """Unanimous YES on pass_on_no records fails the gate but stays a valid measurement.

    This is the 2026-08-17 false alarm in test form: exit 1 with status 'gate_failed'
    means the pass completed and quality was below target, NOT that the harness broke.
    """
    code, gen_dir = _run_panel(tmp_path, score=True)
    status = json.loads((gen_dir / "run_status.json").read_text(encoding="utf-8"))

    assert code == 1
    assert status["status"] == "gate_failed"
    assert status["cases_passed"] < status["cases_total"]
    assert status["error"] == ""


def test_panel_cli_missing_transcript_is_an_error(tmp_path: Path) -> None:
    """A genuinely broken run reports status 'error' — the only status that halts ops."""
    out = tmp_path / "gen" / "judged.jsonl"
    code = judge_runner.main([
        "--transcript", str(tmp_path / "nope.jsonl"),
        "--reports", str(tmp_path / "reports"),
        "--json-out", str(out),
    ])
    status = json.loads((out.parent / "run_status.json").read_text(encoding="utf-8"))

    assert code == 2
    assert status["status"] == "error"
    assert "not found" in status["error"].lower()
