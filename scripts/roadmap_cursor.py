"""
Module: roadmap_cursor
Layer: harness
Purpose: The ONLY reader and writer of the overnight loop's roadmap grammar — finds the
    next actionable task, slices one phase's body, ticks a task, and audits the queue.
Dependencies: scripts/_roadmap_cursor_core (pure logic), stdlib argparse/pathlib/os.
Used by: scripts/expand_loop.sh, .claude/commands/expand-linear-next.md, `make roadmap-verify`.

Both the loop and the skill go through this CLI; nothing else parses ROADMAP.md. That
one-parser rule is why a marker written by ``--mark`` always parses back on the next run.

**CRLF is load-bearing here.** ROADMAP.md is 1183/1183 CRLF with ``core.autocrlf=false``.
The upstream kit used ``Path.read_text``/``write_text``, whose universal-newline handling
would silently rewrite every line LF on each ``--mark`` — turning one-line task commits
into whole-file diffs and destroying the "the commit is the transaction" property. Every
read and write below therefore passes ``newline=""``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _roadmap_cursor_core import (  # noqa: E402
    RoadmapCursorError,
    compute_next,
    fence_bounds,
    find_task,
    parse_roadmap,
    render_marked,
    slice_range,
    verify,
)

DEFAULT_ROADMAP = "project-harness/ROADMAP.md"
ALL_DONE = "ALL_DONE"
EXIT_USAGE = 2


def _roadmap_path() -> Path:
    """Resolve the roadmap path from ``ROADMAP_FILE`` or the repo-relative default."""
    override = os.environ.get("ROADMAP_FILE", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / DEFAULT_ROADMAP


def _read(path: Path) -> list[str]:
    """Read physical lines, preserving each line's original terminator."""
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read().splitlines(keepends=True)


def _write(path: Path, lines: list[str]) -> None:
    """Atomically replace ``path`` with ``lines``, preserving terminators verbatim."""
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8", newline="") as handle:
        handle.write("".join(lines))
    os.replace(temp_path, path)


def _cmd_next(lines: list[str], after: str | None, exclude: frozenset[str]) -> str:
    """Render the ``--next`` / ``--next-after`` answer."""
    phases = parse_roadmap(lines)
    found = compute_next(phases, after=after, exclude=exclude)
    if found is None:
        return ALL_DONE
    phase, task = found
    remaining = len(phase.pending)
    return f"PHASE={phase.id} TASK={task.id} PHASE_REMAINING={remaining}"


def _cmd_status(lines: list[str]) -> str:
    """Render a one-line-per-phase queue summary, plus a totals line."""
    phases = parse_roadmap(lines)
    rows: list[str] = []
    total_open = total_done = total_flagged = 0
    for phase in phases:
        done = sum(1 for t in phase.tasks if t.done)
        flagged = sum(1 for t in phase.tasks if t.skippable and not t.done)
        openx = sum(1 for t in phase.tasks if not t.done and not t.skippable)
        total_open += openx
        total_done += done
        total_flagged += flagged
        state = "DONE" if phase.is_done else "OPEN"
        rows.append(f"{state:4s} {phase.id:12s} open={openx} done={done} flagged={flagged}")
    rows.append(f"TOTAL open={total_open} done={total_done} flagged={total_flagged}")
    return "\n".join(rows)


def _cmd_flagged(lines: list[str]) -> str:
    """List every not-done task the loop will refuse to auto-attempt, with its reasons."""
    phases = parse_roadmap(lines)
    rows = [
        f"{task.id}\t{','.join(sorted(task.flags))}"
        for phase in phases
        for task in phase.tasks
        if task.skippable and not task.done
    ]
    return "\n".join(rows)


def _cmd_phase_done(lines: list[str], phase_id: str) -> int:
    """Exit 0 iff every task in ``phase_id`` is done or flagged (roadmap state, not tokens)."""
    phases = parse_roadmap(lines)
    matches = [p for p in phases if p.id == phase_id]
    if not matches:
        print(f"phase {phase_id} not found", file=sys.stderr)
        return EXIT_USAGE
    return 0 if matches[0].is_done else 1


def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI parser (one mutually exclusive action per invocation)."""
    parser = argparse.ArgumentParser(description="Overnight-loop roadmap cursor.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--next", action="store_true", help="next actionable phase+task")
    action.add_argument("--next-after", metavar="PHASE", help="resume forward from PHASE")
    action.add_argument("--slice", metavar="PHASE", help="print only PHASE's body")
    action.add_argument("--mark", metavar="TASK", help="tick TASK and append a marker")
    action.add_argument("--verify", action="store_true", help="audit the queue's grammar")
    action.add_argument("--status", action="store_true", help="per-phase queue summary")
    action.add_argument("--list-flagged", action="store_true", help="tasks the loop will skip")
    action.add_argument("--phase-done", metavar="PHASE", help="exit 0 if PHASE is complete")
    parser.add_argument("--date", default="", help="ISO date for --mark")
    parser.add_argument("--unverified", default=None, help="mark as UNVERIFIED with this reason")
    parser.add_argument("--exclude", default="", help="comma-separated phase ids to skip")
    return parser


def _dispatch(args: argparse.Namespace, path: Path, lines: list[str]) -> int:
    """Execute the selected action; returns the process exit code."""
    exclude = frozenset(x for x in args.exclude.split(",") if x)
    if args.next or args.next_after:
        print(_cmd_next(lines, args.next_after, exclude))
        return 0
    if args.slice:
        start, end = slice_range(parse_roadmap(lines), args.slice)
        sys.stdout.write("".join(lines[start:end]))
        return 0
    if args.mark:
        if not args.date:
            print("--mark requires --date", file=sys.stderr)
            return EXIT_USAGE
        task = find_task(parse_roadmap(lines), args.mark)
        _write(path, render_marked(lines, task, args.date, args.unverified))
        print(f"MARKED={args.mark}")
        return 0
    if args.status:
        print(_cmd_status(lines))
        return 0
    if args.list_flagged:
        print(_cmd_flagged(lines))
        return 0
    if args.phase_done:
        return _cmd_phase_done(lines, args.phase_done)
    findings = verify(parse_roadmap(lines), lines)
    low, high = fence_bounds(lines)
    for finding in findings:
        print(f"ROADMAP: {finding}", file=sys.stderr)
    if findings:
        return 1
    print(f"ROADMAP OK (queue lines {low + 1}-{high}, {len(parse_roadmap(lines))} phases)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run one action, and map cursor errors onto exit codes."""
    args = _build_parser().parse_args(argv)
    path = _roadmap_path()
    try:
        lines = _read(path)
        return _dispatch(args, path, lines)
    except RoadmapCursorError as error:
        print(f"ROADMAP ERROR [{error.kind}]: {error}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"ROADMAP ERROR [missing]: {path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
