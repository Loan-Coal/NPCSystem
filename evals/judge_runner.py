"""
Module: judge_runner
Layer: evals (eval harness — not part of src/)
Purpose: Judge pass of the two-phase eval pipeline. Reads a TranscriptFile written
         by generate_runner, scores each GenerationRecord via _run_binary_judge,
         applies expected_polarity to derive pass/fail, and feeds the results into
         the existing summary + report pipeline.
Dependencies: argparse, pathlib, sys; matchers (_run_binary_judge), eval_records
         (read_transcript, JudgedRecord), summary (summarize, format_summary_lines),
         report (write_report)
Used by: Makefile eval-judge target
Does NOT: call /v1/dialogue, modify graph state, import from src/npc_engine/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import judge_config
import matchers
from eval_records import GenerationRecord, JudgedRecord, read_transcript
from report import write_report
from summary import format_summary_lines, summarize


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PASS_ON_YES: str = "pass_on_yes"
_PASS_ON_NO: str = "pass_on_no"
_JSONL_ENCODING: str = "utf-8"
_RECORD_ID_COLON_SEGMENTS: int = 2


# ---------------------------------------------------------------------------
# JSONL persistence
# ---------------------------------------------------------------------------


def _write_judged_jsonl(
    judged_records: list[JudgedRecord],
    path: Path,
    judge_model: str,
) -> None:
    """Write one JSONL row per JudgedRecord to path.

    Each row contains: record_id, case_id (prefix of record_id), judge_kind,
    passed, score, detail, judge_model, and repetition. score=null signals an
    infra failure and is distinguishable from a genuine fail (score=false).
    Creates parent directories if needed; overwrites any existing file.

    Args:
        judged_records: Scored records from a judge pass.
        path: Destination .jsonl file (e.g. evals/generations/<gen_id>/judged.jsonl).
        judge_model: Name of the LLM model used in this judge run — recorded on
            every row so a transcript judged twice by different models stays
            attributable (ISSUE-129 traceability requirement).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "record_id": r.record_id,
            "case_id": r.record_id.rsplit(":", _RECORD_ID_COLON_SEGMENTS)[0],
            "judge_kind": r.judge_kind,
            "passed": r.passed,
            "score": r.score,
            "detail": r.reasoning,
            "judge_model": judge_model,
            "repetition": r.repetition,
        }
        for r in judged_records
    ]
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding=_JSONL_ENCODING,
    )


# ---------------------------------------------------------------------------
# Polarity application
# ---------------------------------------------------------------------------


def _apply_polarity(score: bool | None, polarity: str) -> bool:
    """Map a YES/NO judge score to pass/fail given the record's expected_polarity.

    score=None (infra failure) always yields passed=False (inconclusive is not a pass).

    Args:
        score: Raw judge verdict (True=YES, False=NO, None=infra failure).
        polarity: "pass_on_yes" or "pass_on_no".
    Returns:
        True when the verdict satisfies the expectation.
    """
    if score is None:
        return False
    if polarity == _PASS_ON_YES:
        return score is True
    return score is False  # pass_on_no: NO verdict = did not affirm = PASS


# ---------------------------------------------------------------------------
# Result dict adapter
# ---------------------------------------------------------------------------


def _to_result_dict(judged: JudgedRecord) -> dict:
    """Adapt a JudgedRecord to the result dict shape expected by summary.summarize.

    The shape mirrors runner._run_case output:
    {case_id, description, passed, expectations: [{kind, passed, skipped, detail}],
     response, error}.

    Args:
        judged: A scored JudgedRecord.
    Returns:
        Result dict consumable by summary.summarize and report.write_report.
    """
    exp_result: dict = {
        "kind": judged.judge_kind or "none",
        "passed": judged.passed,
        "skipped": False,
        "detail": judged.reasoning or "",
    }
    if judged.score is None:
        exp_result["inconclusive"] = True

    return {
        "case_id": judged.record_id,
        "description": f"[{judged.source}] {judged.npc_id}",
        "passed": judged.passed,
        "expectations": [exp_result],
        "response": {"npc_response": judged.npc_response},
        "error": None,
    }


# ---------------------------------------------------------------------------
# Core judge pass
# ---------------------------------------------------------------------------


def _score_record(record: GenerationRecord) -> JudgedRecord:
    """Score one GenerationRecord via the binary judge and apply polarity.

    Calls matchers._run_binary_judge with the stored criteria and npc_response,
    then maps the YES/NO verdict to pass/fail using expected_polarity.

    Args:
        record: GenerationRecord with judge_kind != None and a valid criteria string.
    Returns:
        JudgedRecord with passed/score/reasoning populated.
    """
    result = matchers._run_binary_judge(record.criteria, record.npc_response)
    passed = _apply_polarity(result.score, record.expected_polarity)
    return JudgedRecord(
        **record.model_dump(),
        passed=passed,
        score=result.score,
        reasoning=result.error or "",
    )


def judge_transcript(path: Path) -> list[JudgedRecord]:
    """Load a transcript and score every record that has a judge_kind.

    Records with judge_kind=None (deterministic grounded checks) are skipped
    — they are not subject to LLM judging and should be evaluated by the
    direct runner path.

    Args:
        path: Path to a transcript file written by generate_runner.
    Returns:
        List of JudgedRecords (one per judged record; None-kind records absent).
    """
    tf = read_transcript(path)
    return [_score_record(r) for r in tf.records if r.judge_kind is not None]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Parse args, run the judge pass, write a report.

    Args:
        argv: CLI argument list (defaults to sys.argv[1:]).
    Returns:
        0 on success, 1 if any cases failed, 2 on error.
    """
    parser = argparse.ArgumentParser(description="NPC Engine eval judge pass")
    parser.add_argument(
        "--transcript",
        required=True,
        type=Path,
        help="Path to transcript file written by eval-generate.",
    )
    parser.add_argument("--reports", default="evals/reports", type=Path)
    parser.add_argument(
        "--json-out",
        dest="json_out",
        type=Path,
        default=None,
        help=(
            "Write one JSONL row per judged record to this path. "
            "Conventional location: evals/generations/<gen_id>/judged.jsonl."
        ),
    )
    args = parser.parse_args(argv)

    if not args.transcript.exists():
        print(f"Transcript not found: {args.transcript}", file=sys.stderr)
        return 2

    try:
        judged_records = judge_transcript(args.transcript)
    except Exception as exc:
        print(f"Failed to load transcript: {exc}", file=sys.stderr)
        return 2

    if args.json_out is not None:
        _write_judged_jsonl(
            judged_records,
            args.json_out,
            judge_config.resolve_judge_model(),
        )

    result_dicts = [_to_result_dict(r) for r in judged_records]
    report_path = write_report(results=result_dicts, output_dir=args.reports)

    run_summary = summarize(result_dicts)
    for line in format_summary_lines(run_summary):
        print(line)

    passed = sum(1 for r in result_dicts if r["passed"])
    total = len(result_dicts)
    print(f"\n{passed}/{total} judged records passed. Report: {report_path}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
