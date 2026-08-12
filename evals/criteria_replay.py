"""
Module: criteria_replay
Layer: evals (eval harness — not part of src/)
Purpose: Re-score selected calibration label rows' stored output_text against
         a NEW criteria file, without a full judge pass over the whole
         transcript. Makes every future judge-criteria change verifiable on a
         small subset (e.g. the discordant rows) instead of a 2.5 h panel
         pass (EVAL-P19.0b).
Dependencies: pydantic, pathlib, yaml, matchers (_run_binary_judge),
              calibration_records
Used by: evals/__main__.py (verb 'replay-criteria'), make eval-replay-criteria
Does NOT: call /v1/dialogue, modify graph state, write to the labels file —
          purely reads a labels file and a criteria YAML, issues judge calls,
          and reports agreement. The caller decides whether to act on the result.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import yaml
from pydantic import BaseModel, ConfigDict

import matchers
from calibration_records import LABELS_FILE, CalibrationLabel, read_calibration_labels

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class ReplayRow(BaseModel):
    """One row's replay outcome: stored verdict vs verdict under new criteria.

    Attributes:
        record_id: The row's record_id.
        human_verdict: Ground truth, or None if this row is not yet adjudicated.
        old_verdict: scorer_verdict as stored on disk before this replay.
        new_verdict: Verdict computed against the new criteria (None = infra failure).
        changed: True if new_verdict != old_verdict.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    human_verdict: bool | None
    old_verdict: bool
    new_verdict: bool | None
    changed: bool


class ReplayResult(BaseModel):
    """Outcome of replaying a criteria change over a selected row set.

    Attributes:
        rows: Per-row replay results, in selection order.
        n_replayed: Number of judge calls issued (== len(rows)).
        n_changed: Rows whose verdict flipped under the new criteria.
        n_adjudicated: Rows with a human_verdict set — the agreement denominator.
        n_agree_with_human: Adjudicated rows where new_verdict == human_verdict.
    """

    model_config = ConfigDict(frozen=True)

    rows: tuple[ReplayRow, ...]
    n_replayed: int
    n_changed: int
    n_adjudicated: int
    n_agree_with_human: int


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def load_criteria_text(path: Path) -> str:
    """Load a criteria string from a judge-criteria YAML file.

    Args:
        path: Path to a YAML file with a top-level `criteria` key (the same
            shape as prompts/eval/refusal_judge.yaml).
    Returns:
        The criteria string.
    Raises:
        FileNotFoundError: If path does not exist.
        KeyError: If the YAML has no `criteria` key.
    """
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return str(data["criteria"])


def select_rows(
    rows: Sequence[CalibrationLabel],
    *,
    scorer: str,
    record_ids: Sequence[str] | None = None,
) -> list[CalibrationLabel]:
    """Filter rows to one scorer, optionally to an explicit record_id subset.

    Args:
        rows: All calibration label rows.
        scorer: Only rows for this scorer are selected.
        record_ids: If given, further restrict to these record_ids — this is
            what keeps a replay of 12 discordant rows from touching the other
            381.
    Returns:
        Selected rows, in original order.
    """
    subset = [r for r in rows if r.scorer == scorer]
    if record_ids is not None:
        wanted = set(record_ids)
        subset = [r for r in subset if r.record_id in wanted]
    return subset


def _replay_one_row(row: CalibrationLabel, criteria_text: str) -> ReplayRow:
    """Score one row's stored output_text against criteria_text.

    Issues exactly one matchers._run_binary_judge call.

    Args:
        row: The row to replay.
        criteria_text: The new criteria to score against.
    Returns:
        ReplayRow with the old and new verdicts and whether they differ.
    """
    verdict = matchers._run_binary_judge(criteria_text, row.output_text).score
    return ReplayRow(
        record_id=row.record_id,
        human_verdict=row.human_verdict,
        old_verdict=row.scorer_verdict,
        new_verdict=verdict,
        changed=verdict != row.scorer_verdict,
    )


def replay_criteria(
    rows: Sequence[CalibrationLabel],
    criteria_text: str,
) -> ReplayResult:
    """Re-score each row's stored output_text against criteria_text.

    Issues exactly one matchers._run_binary_judge call per row — never re-reads
    a transcript, never re-runs generation. Agreement is computed only over
    rows that already carry a human_verdict.

    Args:
        rows: Rows to replay (see select_rows to build a subset).
        criteria_text: The new criteria to score against.
    Returns:
        ReplayResult with per-row outcomes and aggregate agreement counts.
    """
    replayed = [_replay_one_row(row, criteria_text) for row in rows]
    adjudicated = [r for r in replayed if r.human_verdict is not None]
    return ReplayResult(
        rows=tuple(replayed),
        n_replayed=len(replayed),
        n_changed=sum(1 for r in replayed if r.changed),
        n_adjudicated=len(adjudicated),
        n_agree_with_human=sum(1 for r in adjudicated if r.new_verdict == r.human_verdict),
    )


def format_replay_report(result: ReplayResult, criteria_path: Path) -> str:
    """Render a human-readable summary of a replay.

    Args:
        result: Outcome from replay_criteria.
        criteria_path: The criteria file that was replayed against.
    Returns:
        Multi-line report string.
    """
    lines = [
        f"Replayed {result.n_replayed} row(s) against {criteria_path}",
        f"  changed vs stored scorer_verdict: {result.n_changed}",
    ]
    if result.n_adjudicated:
        rate = result.n_agree_with_human / result.n_adjudicated
        lines.append(
            f"  agreement with human_verdict: {result.n_agree_with_human}/"
            f"{result.n_adjudicated} ({rate:.1%})"
        )
    else:
        lines.append("  agreement with human_verdict: n/a (no adjudicated rows selected)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the replay-criteria CLI."""
    parser = argparse.ArgumentParser(
        description="Re-score selected calibration rows against a new criteria file."
    )
    parser.add_argument("--criteria-file", required=True, type=Path)
    parser.add_argument("--scorer", required=True)
    parser.add_argument("--labels-file", type=Path, default=LABELS_FILE)
    parser.add_argument(
        "--record-ids",
        default=None,
        help="Comma-separated record_ids to restrict the replay to; default is every "
        "row for --scorer.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: replay a criteria file over selected labels file rows.

    Usage:
        python evals/criteria_replay.py --criteria-file PATH --scorer NAME
            [--labels-file PATH] [--record-ids ID,ID,...]
        python -m evals replay-criteria ...

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].
    Returns:
        0 on success, 1 if the labels or criteria file does not exist.
    """
    args = _build_parser().parse_args(argv)

    if not args.labels_file.exists():
        print(f"ERROR: Labels file not found: {args.labels_file}", file=sys.stderr)
        return 1
    if not args.criteria_file.exists():
        print(f"ERROR: Criteria file not found: {args.criteria_file}", file=sys.stderr)
        return 1

    record_ids = args.record_ids.split(",") if args.record_ids else None
    rows = read_calibration_labels(args.labels_file)
    selected = select_rows(rows, scorer=args.scorer, record_ids=record_ids)
    criteria_text = load_criteria_text(args.criteria_file)
    result = replay_criteria(selected, criteria_text)
    print(format_replay_report(result, args.criteria_file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
