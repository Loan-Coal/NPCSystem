"""
Module: check_human_gates
Layer: harness
Purpose: Parse the `#### HUMAN GATE` blocks interleaved through ROADMAP.md and refuse to
    hand the overnight loop a task that sits behind a gate a human has not cleared.
Dependencies: stdlib argparse/os/re/sys/pathlib; pydantic (frozen models, project rule).
Used by: scripts/expand_loop.sh (per-task `--check`), `make check-human-gates`,
    tests/unit/scripts/test_check_human_gates.py.

Why this exists (DEC-164). `compute_next` skips a flagged task and walks on — it enforces
no dependency at all. So the loop runs straight past every `(live` / ⏸️ human task and
finishes the fence with the measurements still unmade. The flags say *"not you"*; nothing
said *"not yet"*. A gate says the second: until the human work named in `Clears when` is
ticked, the tasks named in `Blocks` are not startable by anyone, loop or session.

The grammar is deliberately three id lists and nothing else, because a gate that needs
prose to be evaluated is a gate no script can enforce.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict

# --- grammar (every magic string named) --------------------------------------------
GATE_HEADING_RE = re.compile(r"^#### (?:\W*\s*)?HUMAN GATE (H\d+)\s*[-—]\s*(.*?)\s*$")
FIELD_RE = re.compile(r"^\*\*([A-Za-z ]+):\*\*\s*(.*?)\s*$")
TASK_BULLET_RE = re.compile(r"^- \[([ xX])\]\s+\*\*([A-Za-z0-9][A-Za-z0-9._-]*)\*\*")
TASK_ID_RE = re.compile(r"EVAL-P\d+\.\d+[a-z]?")
BLOCK_END_RE = re.compile(r"^(?:- \[[ xX]\]|#{1,4} )")

FIELD_READY = "Ready when"
FIELD_CLEARS = "Clears when"
FIELD_BLOCKS = "Blocks"
FIELD_RUNBOOK = "Runbook"
REQUIRED_FIELDS = (FIELD_READY, FIELD_CLEARS, FIELD_BLOCKS, FIELD_RUNBOOK)

DEFAULT_ROADMAP = "project-harness/ROADMAP.md"
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


class HumanGate(BaseModel):
    """One `#### HUMAN GATE Hn` block: the ids it waits on, clears on, and blocks."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    line: int
    ready_when: tuple[str, ...]
    clears_when: tuple[str, ...]
    blocks: tuple[str, ...]
    runbook: str
    missing_fields: tuple[str, ...]

    @property
    def requirements(self) -> tuple[str, ...]:
        """Every id that must be ticked before downstream work may start.

        A barrier gate (`Clears when: -`) has no task of its own, so its ready set is
        its whole requirement — that is how the fence-reopen gate is expressed.
        """
        return self.ready_when + self.clears_when

    def is_ready(self, states: dict[str, bool]) -> bool:
        """True when the human can start this gate's work — prerequisites all ticked."""
        return all(states.get(task, False) for task in self.ready_when)

    def is_open(self, states: dict[str, bool]) -> bool:
        """True when every requirement is ticked, so `blocks` no longer applies."""
        return all(states.get(task, False) for task in self.requirements)


def _ids(value: str) -> tuple[str, ...]:
    """Task ids in a field value; an em-dash or `none` yields an empty tuple."""
    return tuple(TASK_ID_RE.findall(value))


def _fields(lines: list[str], start: int) -> dict[str, str]:
    """Read the `**Field:** value` lines directly under a gate heading."""
    found: dict[str, str] = {}
    for index in range(start + 1, len(lines)):
        if BLOCK_END_RE.match(lines[index]):
            break
        match = FIELD_RE.match(lines[index])
        if match:
            found[match.group(1).strip()] = match.group(2)
    return found


def parse_gates(lines: list[str]) -> tuple[HumanGate, ...]:
    """Parse every gate block in the whole file, in file order.

    Args:
        lines: Physical lines of the roadmap.
    Returns:
        The gates, file order. Gates outside the LOOP:QUEUE fence are included — the
        fence bounds what the *loop* may run, not what a human must clear.
    """
    gates: list[HumanGate] = []
    for index, line in enumerate(lines):
        match = GATE_HEADING_RE.match(line)
        if not match:
            continue
        fields = _fields(lines, index)
        gates.append(
            HumanGate(
                id=match.group(1),
                title=match.group(2),
                line=index + 1,
                ready_when=_ids(fields.get(FIELD_READY, "")),
                clears_when=_ids(fields.get(FIELD_CLEARS, "")),
                blocks=_ids(fields.get(FIELD_BLOCKS, "")),
                runbook=fields.get(FIELD_RUNBOOK, ""),
                missing_fields=tuple(f for f in REQUIRED_FIELDS if f not in fields),
            )
        )
    return tuple(gates)


def task_states(lines: list[str]) -> dict[str, bool]:
    """Map every `- [ ] **ID**` task in the whole file to its ticked state.

    Deliberately not fence-scoped: gates reference EVAL-P20..P24, which sit outside
    the loop queue and are invisible to `_roadmap_cursor_core.parse_roadmap`.
    """
    states: dict[str, bool] = {}
    for line in lines:
        match = TASK_BULLET_RE.match(line)
        if match:
            states[match.group(2)] = match.group(1).lower() == "x"
    return states


def blocked_tasks(gates: tuple[HumanGate, ...], states: dict[str, bool]) -> dict[str, str]:
    """Map each blocked task id to the id of the first closed gate blocking it."""
    blocked: dict[str, str] = {}
    for gate in gates:
        if gate.is_open(states):
            continue
        for task in gate.blocks:
            blocked.setdefault(task, gate.id)
    return blocked


def verify_gates(gates: tuple[HumanGate, ...], states: dict[str, bool]) -> list[str]:
    """Return every grammar finding; an empty list means the gate set is well-formed."""
    findings: list[str] = []
    seen: set[str] = set()
    for gate in gates:
        where = f"gate {gate.id} (line {gate.line})"
        if gate.id in seen:
            findings.append(f"{where}: duplicate gate id")
        seen.add(gate.id)
        for field in gate.missing_fields:
            findings.append(f"{where}: missing required field '{field}'")
        if not gate.requirements:
            findings.append(f"{where}: no 'Ready when' or 'Clears when' ids — unenforceable")
        for task in set(gate.requirements) | set(gate.blocks):
            if task not in states:
                findings.append(f"{where}: references unknown task id {task}")
        findings.extend(_self_block_findings(gate, where))
    return findings


def _self_block_findings(gate: HumanGate, where: str) -> list[str]:
    """A gate that blocks its own clearing task can never open."""
    overlap = sorted(set(gate.blocks) & set(gate.requirements))
    return [f"{where}: blocks its own requirement {task}" for task in overlap]


def _roadmap_path() -> Path:
    """Resolve the roadmap path from `ROADMAP_FILE` or the repo-relative default."""
    override = os.environ.get("ROADMAP_FILE", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / DEFAULT_ROADMAP


def _read(path: Path) -> list[str]:
    """Read physical lines, preserving each line's original terminator (CRLF is load-bearing)."""
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read().splitlines(keepends=True)


def _state_label(gate: HumanGate, states: dict[str, bool]) -> str:
    """One word for the report: OPEN, READY (do it now), or WAITING."""
    if gate.is_open(states):
        return "OPEN"
    return "READY" if gate.is_ready(states) else "WAITING"


def _render_report(gates: tuple[HumanGate, ...], states: dict[str, bool]) -> str:
    """Human-readable one-block-per-gate summary, in execution order.

    Sorted by gate number, not file position: H11 (`EVAL-P8.3`) sits in Program 1 near
    the top of the roadmap but is the last thing you do, and a report in file order
    would read as a work queue that starts with the task you must not run yet.
    """
    rows: list[str] = []
    for gate in sorted(gates, key=lambda g: int(g.id[1:])):
        label = _state_label(gate, states)
        rows.append(f"{label:8s} {gate.id:4s} {gate.title}")
        if label != "OPEN":
            outstanding = [t for t in gate.requirements if not states.get(t, False)]
            rows.append(f"{'':8s}      outstanding: {', '.join(outstanding) or 'none'}")
            rows.append(f"{'':8s}      runbook:     {gate.runbook}")
    blocked = blocked_tasks(gates, states)
    rows.append(f"TOTAL gates={len(gates)} blocked_tasks={len(blocked)}")
    return "\n".join(rows)


def _cmd_check(gates: tuple[HumanGate, ...], states: dict[str, bool], task_id: str) -> int:
    """Exit non-zero when `task_id` sits behind a closed gate, naming that gate."""
    blocked = blocked_tasks(gates, states)
    gate_id = blocked.get(task_id)
    if gate_id is None:
        return EXIT_OK
    gate = next(g for g in gates if g.id == gate_id)
    outstanding = ", ".join(t for t in gate.requirements if not states.get(t, False))
    print(
        f"HUMAN GATE {gate.id} is closed: {task_id} must not start.\n"
        f"  gate:        {gate.title} (ROADMAP.md line {gate.line})\n"
        f"  outstanding: {outstanding}\n"
        f"  runbook:     {gate.runbook}",
        file=sys.stderr,
    )
    return EXIT_FAIL


def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI parser (one action per invocation; default is the report)."""
    parser = argparse.ArgumentParser(description="Human-gate checker for the overnight loop.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", metavar="TASK", help="exit 1 if TASK is behind a closed gate")
    action.add_argument("--verify", action="store_true", help="audit the gate grammar")
    action.add_argument("--blocked", action="store_true", help="list blocked task ids")
    return parser


def _force_utf8_streams() -> None:
    """Reconfigure stdout/stderr to UTF-8 so a report glyph cannot crash the check.

    Gate titles carry κ and ≥. On a Windows console defaulting to cp1252 those raise
    UnicodeEncodeError, which would turn a green gate check into a loop halt for a
    reason that has nothing to do with the gates. Mirrors `evals/__main__`.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass  # Non-reconfigurable stream (pipe/pytest capture) — leave as-is.


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run one action, and map failures onto exit codes."""
    _force_utf8_streams()
    args = _build_parser().parse_args(argv)
    path = _roadmap_path()
    try:
        lines = _read(path)
    except FileNotFoundError:
        print(f"HUMAN GATES ERROR [missing]: {path}", file=sys.stderr)
        return EXIT_FAIL
    gates, states = parse_gates(lines), task_states(lines)
    if args.check:
        return _cmd_check(gates, states, args.check)
    if args.verify:
        findings = verify_gates(gates, states)
        for finding in findings:
            print(f"HUMAN GATES: {finding}", file=sys.stderr)
        if findings:
            return EXIT_FAIL
        print(f"HUMAN GATES OK ({len(gates)} gates)")
        return EXIT_OK
    if args.blocked:
        print("\n".join(sorted(blocked_tasks(gates, states))))
        return EXIT_OK
    print(_render_report(gates, states))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
