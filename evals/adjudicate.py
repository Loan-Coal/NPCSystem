"""
Module: adjudicate
Layer: evals (eval harness — not part of src/)
Purpose: Resumable interactive CLI for human adjudication of CalibrationLabel rows.
         Prints unadjudicated rows one at a time, accepts keep/flip/skip, and writes
         human_verdict + adjudicated_at back to the JSONL file in place.
Dependencies: calibration_records, datetime, pathlib, sys, typing
Used by: CLI (make eval-adjudicate), calibration (EVAL-P5.4)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from calibration_records import (
    LABELS_FILE,
    CalibrationLabel,
    DuplicateLabelKeyError,
    read_calibration_labels,
    write_calibration_labels,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_COMMANDS: frozenset[str] = frozenset({"keep", "flip", "skip"})
SHORTCUTS: dict[str, str] = {"k": "keep", "f": "flip", "s": "skip"}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def collect_pending(rows: Sequence[CalibrationLabel]) -> list[CalibrationLabel]:
    """Return rows needing adjudication: never-judged rows plus drifted rows.

    A drifted row (needs_review=True, written by label_merge.merge_labels)
    already carries a human_verdict, but for content the scorer no longer
    produces — it must be re-presented, not silently trusted. Its previous
    verdict is copied into prior_human_verdict so the adjudicator sees what
    they decided last time (EVAL-P19.0).

    Args:
        rows: All calibration label rows.
    Returns:
        Subset of rows in original order: human_verdict=None rows unchanged,
        plus needs_review rows with prior_human_verdict populated.
    """
    pending: list[CalibrationLabel] = []
    for row in rows:
        if row.human_verdict is None:
            pending.append(row)
        elif row.needs_review:
            pending.append(row.model_copy(update={"prior_human_verdict": row.human_verdict}))
    return pending


def apply_verdict(
    row: CalibrationLabel,
    verdict: str,
    timestamp: str,
) -> CalibrationLabel:
    """Apply a human verdict to a calibration label row.

    Returns a new CalibrationLabel with human_verdict and adjudicated_at set.
    On 'skip', returns the original row unchanged — including needs_review,
    so a drifted row that was skipped stays excluded and pending next time.
    A 'keep'/'flip' verdict resolves drift: needs_review clears and
    prior_human_verdict is cleared back to None, since the row now carries a
    fresh verdict against its current content.

    Args:
        row: The original CalibrationLabel (frozen; never mutated).
        verdict: One of 'keep', 'flip', or 'skip'.
        timestamp: ISO-8601 adjudication timestamp.
    Returns:
        Updated CalibrationLabel, or the original row on 'skip'.
    Raises:
        ValueError: If verdict is not one of the valid commands.
    """
    if verdict not in VALID_COMMANDS:
        raise ValueError(
            f"Invalid verdict {verdict!r}; expected one of {sorted(VALID_COMMANDS)}"
        )
    if verdict == "skip":
        return row
    human_verdict = row.pre_label if verdict == "keep" else not row.pre_label
    return row.model_copy(update={
        "human_verdict": human_verdict,
        "adjudicated_at": timestamp,
        "needs_review": False,
        "prior_human_verdict": None,
    })


# ---------------------------------------------------------------------------
# I/O helpers (injectable for testing)
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _format_row_prompt(row: CalibrationLabel, index: int, total: int) -> str:
    """Return a formatted display string for one adjudication row.

    Shows criteria and, when present, player_message and observed — without
    these an adjudicator judging an in_set/range/schema row cannot see the
    response field the scorer actually inspects, since that field is absent
    from output_text entirely.
    """
    label_str = "PASS" if row.pre_label else "FAIL"
    lines = [f"\n[{index}/{total}] scorer={row.scorer}  record_id={row.record_id}"]
    if row.needs_review and row.prior_human_verdict is not None:
        prior_str = "PASS" if row.prior_human_verdict else "FAIL"
        lines.append(
            f"⚠ DRIFTED: content changed since last adjudication "
            f"(prior human verdict: {prior_str})"
        )
    if row.player_message:
        lines.append(f"player_message:\n  {row.player_message}")
    lines.append(f"criteria:\n  {row.criteria or '(none recorded)'}")
    lines.append(f"pre_label : {label_str}")
    lines.append(f"output_text:\n  {row.output_text}")
    if row.observed:
        lines.append(f"observed:\n  {row.observed}")
    lines.append("")
    lines.append("  keep(k) / flip(f) / skip(s): ")
    return "\n".join(lines)


def _read_command(read_line: Callable[[], str], print_fn: Callable[[str], None]) -> str:
    """Read a valid adjudication command, looping until valid input received.

    Args:
        read_line: Callable that returns one line of user input.
        print_fn: Callable for printing retry prompts.
    Returns:
        Canonical command name: 'keep', 'flip', or 'skip'.
    """
    while True:
        raw = read_line().strip().lower()
        if raw in SHORTCUTS:
            return SHORTCUTS[raw]
        if raw in VALID_COMMANDS:
            return raw
        print_fn(f"  Invalid input {raw!r}. Enter keep/flip/skip or k/f/s.")


def _replace_row(
    all_rows: list[CalibrationLabel],
    old: CalibrationLabel,
    new: CalibrationLabel,
) -> list[CalibrationLabel]:
    """Return a new list with old replaced by new (matched by record_id + scorer).

    Raises:
        DuplicateLabelKeyError: If the key matches more than one row. A
            non-unique match means this single verdict would overwrite someone
            else's verdict as well as its own target — the failure mode that
            `--append`-produced duplicates caused silently.
    """
    matches = sum(
        1 for r in all_rows if r.record_id == old.record_id and r.scorer == old.scorer
    )
    if matches > 1:
        raise DuplicateLabelKeyError(old.record_id, old.scorer)
    return [
        new if (r.record_id == old.record_id and r.scorer == old.scorer) else r
        for r in all_rows
    ]


# ---------------------------------------------------------------------------
# Main adjudication loop
# ---------------------------------------------------------------------------


def run_adjudication(
    path: Path,
    *,
    read_line: Callable[[], str] | None = None,
    print_fn: Callable[[str], None] | None = None,
) -> int:
    """Run the interactive adjudication loop over a JSONL calibration file.

    Loads all rows, skips already-adjudicated ones, presents pending rows one
    by one, and writes the full updated file back after each keep/flip verdict.

    Args:
        path: Path to the JSONL labels file.
        read_line: Callable returning one line of user input; defaults to input().
        print_fn: Callable for output; defaults to print().
    Returns:
        Number of rows where a keep/flip verdict was recorded.
    """
    _read = read_line if read_line is not None else input
    _print = print_fn if print_fn is not None else print

    all_rows = read_calibration_labels(path)
    pending = collect_pending(all_rows)
    total = len(pending)

    if total == 0:
        _print("All rows already adjudicated. Nothing to do.")
        return 0

    _print(f"Loaded {len(all_rows)} rows; {total} pending adjudication.")
    adjudicated_count = 0

    for idx, row in enumerate(pending, start=1):
        _print(_format_row_prompt(row, idx, total))
        verdict = _read_command(_read, _print)
        if verdict == "skip":
            continue
        updated = apply_verdict(row, verdict, _now_iso())
        all_rows = _replace_row(all_rows, row, updated)
        write_calibration_labels(path, all_rows)
        adjudicated_count += 1

    _print(f"\nDone. {adjudicated_count} rows adjudicated this session.")
    return adjudicated_count


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: adjudicate evals/calibration/labels_v1.jsonl.

    Usage:
        python evals/adjudicate.py [--file PATH]
        python -m evals adjudicate [--file PATH]

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Resumable interactive adjudication of calibration labels."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=LABELS_FILE,
        help="Path to labels JSONL (default: evals/calibration/labels_v1.jsonl).",
    )
    args = parser.parse_args(argv)

    if not args.file.exists():
        print(f"ERROR: Labels file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    run_adjudication(args.file)


if __name__ == "__main__":
    main()
