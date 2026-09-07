"""
Module: judge_runner
Layer: evals (eval harness — not part of src/)
Purpose: Judge pass of the two-phase eval pipeline. Reads a TranscriptFile written
         by generate_runner, scores each GenerationRecord via _run_binary_judge, and
         applies expected_polarity to derive pass/fail. Result-dict adaptation and
         per-case grouping (EVAL-P6.2 — closes ISSUE-123's guard-turn double count)
         live in judge_case_grouping; panel scoring lives in judge_panel_runner
         (split out to stay under the 300-line cap); this module owns the
         single-judge scoring path and the CLI.
         --panel switches to the 3-model judge panel (EVAL-P21.1/P21.2, DEC-183/184):
         every judge_kind record is scored by every panel seat, consensus requires
         >=2-of-3 to fail, and every seat's verdict is persisted rather than only
         the winning one — see judge_panel_runner for the implementation.
         Row persistence lives in judged_persistence (the single owner of the
         judged.jsonl schema, DEC-187); artifact paths and RunStatus assembly live
         in judge_run_artifacts; agreement statistics live in panel_metrics.
Dependencies: argparse, pathlib, sys; matchers (_run_binary_judge), eval_records
         (read_transcript, JudgedRecord), judge_case_grouping (group_by_case),
         judge_panel_runner (judge_transcript_panel), judge_run_artifacts
         (build_status, panel_votes_path, record_error, status_path_for),
         judged_persistence (write_consensus_jsonl, write_judged_jsonl,
         write_seat_votes_jsonl), panel_metrics (compute_panel_metrics),
         judge_config (resolve_judge_panel), run_status (write_run_status),
         summary (summarize, format_summary_lines), report (write_report)
Used by: Makefile eval-judge target
Does NOT: call /v1/dialogue, modify graph state, import from src/npc_engine/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import judge_config
import matchers
from eval_records import GenerationRecord, JudgedRecord, read_transcript
from judge_case_grouping import group_by_case
from judge_panel_runner import judge_transcript_panel
from judge_run_artifacts import build_status, panel_votes_path, record_error, status_path_for
from judged_persistence import write_consensus_jsonl, write_judged_jsonl, write_seat_votes_jsonl
from panel_metrics import PanelMetrics, compute_panel_metrics
from report import write_report
from run_status import write_run_status
from summary import format_summary_lines, summarize


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PASS_ON_YES: str = "pass_on_yes"


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


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the judge-runner CLI."""
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
    parser.add_argument(
        "--status-out",
        dest="status_out",
        type=Path,
        default=None,
        help=(
            "Write a machine-readable run_status.json here. Defaults to "
            "<json-out dir>/run_status.json when --json-out is given. Ops scripts "
            "should branch on its 'status' field, never on the exit code."
        ),
    )
    parser.add_argument(
        "--panel",
        action="store_true",
        help=(
            "Judge every record through the 3-model panel (>=2-of-3 to fail) "
            "instead of a single judge. --json-out keeps the one-row-per-record "
            "consensus shape; a sibling judged_panel_votes.jsonl carries one row "
            "per judge per record (DEC-187)."
        ),
    )
    parser.add_argument(
        "--panel-models",
        default=None,
        metavar="MODEL,MODEL,MODEL",
        help=(
            "Comma-separated panel roster override; validated the same way as "
            "the default (judge_config.resolve_judge_panel). Ignored without --panel."
        ),
    )
    return parser


def _run_judging(
    args: argparse.Namespace,
) -> tuple[list[JudgedRecord], PanelMetrics | None, tuple[str, ...], str]:
    """Run either the single-judge or panel pass per CLI args, writing --json-out.

    Panel mode writes TWO files (ISSUE-175, option (b)): --json-out keeps the
    historical one-row-per-record consensus shape every existing reader expects,
    and a sibling judged_panel_votes.jsonl carries one row per seat per record
    for auditability. Both are written by judged_persistence, which owns the
    shared schema.

    Args:
        args: Parsed CLI namespace (transcript, json_out, panel, panel_models).
    Returns:
        (judged_records, panel_metrics — None outside --panel mode, panel roster,
        single-judge model name — empty in panel mode).
    """
    if not args.panel:
        judged_records = judge_transcript(args.transcript)
        judge_model = judge_config.resolve_judge_model()
        if args.json_out is not None:
            write_judged_jsonl(judged_records, args.json_out, judge_model)
        return judged_records, None, (), judge_model

    requested = tuple(args.panel_models.split(",")) if args.panel_models else None
    models = tuple(judge_config.resolve_judge_panel(requested=requested))
    judged_records, scored = judge_transcript_panel(args.transcript, models)
    if args.json_out is not None:
        write_consensus_jsonl(judged_records, args.json_out, panel_size=len(models))
        write_seat_votes_jsonl(scored, panel_votes_path(args.json_out))
    return judged_records, compute_panel_metrics(scored), models, ""


def _render_report(
    result_dicts: list[dict],
    reports_dir: Path,
    panel_metrics: PanelMetrics | None,
) -> tuple[Path | None, str]:
    """Write the markdown report and print the console summary.

    A generation with guard cases and zero capability cases (or vice versa)
    trips summary._assert_paired_rates — a real, valid shape, not a bug in
    that function (ISSUE-288). Judging has already completed by the time this
    runs, so a render failure here must not be allowed to lose the pass's
    results: it is caught, not raised, and the caller still gets a
    run_status.json written with real case counts (and panel kappa, if any),
    just without a markdown report.

    Args:
        result_dicts: Grouped per-case results (judge_case_grouping.group_by_case).
        reports_dir: Directory write_report writes its timestamped .md file into.
        panel_metrics: Panel agreement statistics, or None for a single-judge pass.
    Returns:
        (report_path, report_error). On success, report_path is set and
        report_error is "". On failure, report_path is None and report_error
        names what went wrong.
    """
    try:
        report_path = write_report(results=result_dicts, output_dir=reports_dir)
        summary_lines = format_summary_lines(summarize(result_dicts), panel_metrics=panel_metrics)
        for line in summary_lines:
            print(line)
        return report_path, ""
    except Exception as exc:  # quality-ok: boundary — render failure must not lose run_status.json
        message = f"Report generation failed: {exc}"
        print(message, file=sys.stderr)
        return None, message


def main(argv: list[str] | None = None) -> int:
    """Parse args, run the judge pass, write a report and a run_status.json.

    Exit codes are a THREE-way distinction, not a boolean (DEC-189): 0 means the
    gate was met, 1 means the pass completed and some cases did not meet their
    expectations, 2 means the pass could not complete. Only 2 invalidates the
    measurement. Ops scripts should read run_status.json rather than reasoning
    about these codes — reading 1 as a crash is what halted Phase 2 on 2026-08-17.
    A report-render failure (ISSUE-288) does not change this: the judging still
    completed, so exit_code stays 0/1 — see _render_report and run_status.error.

    Args:
        argv: CLI argument list (defaults to sys.argv[1:]).
    Returns:
        0 on success, 1 if any cases failed the gate, 2 on error.
    """
    args = _build_parser().parse_args(argv)

    if not args.transcript.exists():
        return int(record_error(args, f"Transcript not found: {args.transcript}"))

    try:
        judged_records, panel_metrics, panel_models, judge_model = _run_judging(args)
    except Exception as exc:  # quality-ok: boundary — any failure here is an infra error
        return int(record_error(args, f"Judge pass failed: {exc}"))

    result_dicts = group_by_case(judged_records)
    report_path, report_error = _render_report(result_dicts, args.reports, panel_metrics)

    passed = sum(1 for r in result_dicts if r["passed"])
    total = len(result_dicts)
    report_note = f"Report: {report_path}" if report_path else "(no report written; see stderr)"
    print(f"\n{passed}/{total} judged cases passed. {report_note}")

    exit_code = 0 if passed == total else 1
    status_path = status_path_for(args)
    if status_path is not None:
        status = build_status(
            exit_code, passed, total, panel_metrics, panel_models, judge_model,
            report_path, args.json_out,
        )
        if report_error:
            status = status.model_copy(update={"error": report_error})
        write_run_status(status, status_path)
        print(f"Run status: {status_path}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
