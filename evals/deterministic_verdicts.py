"""
Module: deterministic_verdicts
Layer: evals (eval harness — not part of src/)
Purpose: Replay every deterministic (judge_kind=None) record in a transcript through
         its matcher and write judged-format JSONL. Closes the gap that made
         deterministic scorers uncalibratable: deterministic_records.score_record
         could always replay a verdict, but no CLI verb ever persisted one, so
         judged.jsonl held LLM-judge records only and label-import had no
         scorer_verdict to join for the other ~62% of the transcript.
Dependencies: argparse, json, pathlib, sys; eval_records (read_transcript),
         deterministic_records (score_record)
Used by: python -m evals deterministic-verdicts; make eval-deterministic-verdicts
Does NOT: call the LLM judge, call /v1/dialogue, modify graph state

Emits the same row shape judge_runner writes (record_id, repetition, passed,
score, reasoning) so label_import can consume both files through one code path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import deterministic_records
from eval_records import GenerationRecord, read_transcript

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CONFIG_ERROR_PREFIX: str = "EvalConfigError: "


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def verdict_row(record: GenerationRecord) -> dict[str, Any]:
    """Replay one deterministic record's matcher and build its judged-format row.

    A mis-configured expectation (matchers.EvalConfigError) is recorded as a
    failed verdict with the error in `reasoning` rather than aborting the run —
    one bad case must not cost the whole replay pass, and the row stays visible
    for adjudication.

    Args:
        record: A GenerationRecord with judge_kind=None and matcher_kind set.
    Returns:
        Dict with record_id, repetition, matcher_kind, passed, score, reasoning.
    """
    try:
        passed, detail = deterministic_records.score_record(record)
    except Exception as exc:  # noqa: BLE001 — surfaced in the row, never swallowed
        passed, detail = False, f"{_CONFIG_ERROR_PREFIX}{exc}"

    return {
        "record_id": record.record_id,
        "repetition": record.repetition,
        "matcher_kind": record.matcher_kind,
        "passed": passed,
        "score": passed,
        "reasoning": detail,
    }


def build_verdict_rows(records: list[GenerationRecord]) -> list[dict[str, Any]]:
    """Replay every deterministic record in `records`.

    Args:
        records: All records from a generation transcript.
    Returns:
        One verdict row per record with judge_kind=None and matcher_kind set;
        judge records are skipped (judge_runner owns those).
    """
    return [
        verdict_row(r) for r in records if r.judge_kind is None and r.matcher_kind is not None
    ]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the deterministic-verdicts verb."""
    p = argparse.ArgumentParser(
        prog="python -m evals deterministic-verdicts",
        description=(
            "Replay every deterministic matcher record in a transcript and write "
            "judged-format JSONL (no LLM, no engine calls). Produces the "
            "scorer_verdict source that label-import needs for non-judge scorers."
        ),
    )
    p.add_argument(
        "--transcript",
        type=Path,
        required=True,
        metavar="PATH",
        help="Path to the generation transcript's outputs.jsonl.",
    )
    p.add_argument(
        "--json-out",
        type=Path,
        required=True,
        metavar="PATH",
        help="Destination JSONL file (e.g. evals/generations/<id>/deterministic_judged.jsonl).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the deterministic-verdicts verb.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 on success.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    transcript = read_transcript(args.transcript)
    rows = build_verdict_rows(list(transcript.records))

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
        encoding="utf-8",
    )

    failed = sum(1 for r in rows if not r["passed"])
    print(
        f"Replayed {len(rows)} deterministic record(s) "
        f"({len(rows) - failed} passed, {failed} failed) → {args.json_out}",
        file=sys.stderr,
    )
    return 0
