"""
Module: _roadmap_cursor_core
Layer: harness
Purpose: Pure parsing/marking logic for the overnight loop's view of ROADMAP.md — the one
    true understanding of the queue fence, phase/task grammar and DONE markers, so that a
    marker written here always parses back here.
Dependencies: pydantic (v2) only. No I/O, no argparse — every function is pure over a
    list of physical lines produced by ``str.splitlines(keepends=True)``.
Used by: scripts/roadmap_cursor.py (thin CLI), tests/unit/harness/test_roadmap_cursor.py.

Grammar notes specific to THIS repo (they differ from the upstream kit):

* **Done is the checkbox, never the ✅ glyph.** This roadmap uses ✅ freely in prose
  ("DEC-147 ✅ ACCEPTED", "✅ a9a7d0b"), so keying on a ✅ token — as the upstream kit
  does — would mark almost every task done on sight. Only ``- [x]`` means done.
* **Phase ids are strings, not integers** (``EVAL-P0``, ``PERF``, ``H``), so phases are
  ordered by file position rather than numerically.
* **Nothing outside the LOOP:QUEUE fence exists.** 19 open tasks live elsewhere in the
  file (Phase PERF, Phase EVAL, two bullets inside "## Completed", Parked, optional
  PR-9); the fence is what keeps them structurally unreachable at 3am.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

# --- grammar (every magic string named) --------------------------------------------
FENCE_START = "<!-- LOOP:QUEUE start -->"
FENCE_END = "<!-- LOOP:QUEUE end -->"
PHASE_HEADING_RE = re.compile(r"^### Phase ([A-Za-z0-9][A-Za-z0-9._-]*)")
PHASE_HEADING_PREFIX = "### Phase "
TASK_BULLET_RE = re.compile(r"^- \[([ xX])\]\s+\*\*([A-Za-z0-9][A-Za-z0-9._-]*)")
# A task block runs to the next top-level bullet, heading, rule, or the fence end.
BLOCK_END_RE = re.compile(r"^(?:- \[[ xX]\]|#{2,4} |---|<!-- LOOP:QUEUE end)")

# Flags parsed out of a task's body so the loop can skip without spending a session.
ASK_GATE_RE = re.compile(r"ask-gate", re.IGNORECASE)
LIVE_RE = re.compile(r"\(live[;,)\s]", re.IGNORECASE)
DEFERRED_TOKEN = "⏸️"
FLAG_ASK_GATE = "ask-gate"
FLAG_LIVE = "live"
FLAG_DEFERRED = "deferred"

MARKER_TEMPLATE = " ✅ AUTO ({task_id}, {date})"
UNVERIFIED_TEMPLATE = " ✅ AUTO ⚠️ UNVERIFIED ({task_id}, {reason}, {date})"
CHECKED_BOX = "- [x]"
UNCHECKED_BOX = "- [ ]"


class RoadmapCursorError(Exception):
    """Raised when the roadmap cannot be parsed or a requested phase/task is absent."""

    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


class TaskEntry(BaseModel):
    """One ``- [ ] **ID**`` task: its id, phase, done state, skip flags and line span."""

    model_config = ConfigDict(frozen=True)

    id: str
    phase: str
    done: bool
    flags: frozenset[str]
    start: int
    end: int

    @property
    def skippable(self) -> bool:
        """True when a flag says an unattended session must not attempt this task."""
        return bool(self.flags)


class PhaseEntry(BaseModel):
    """One ``### Phase <id>`` section inside the fence: its id, line span and tasks."""

    model_config = ConfigDict(frozen=True)

    id: str
    start: int
    end: int
    tasks: tuple[TaskEntry, ...]

    @property
    def is_done(self) -> bool:
        """A phase is done iff it has tasks and none remain actionable."""
        return bool(self.tasks) and all(t.done or t.skippable for t in self.tasks)

    @property
    def pending(self) -> tuple[str, ...]:
        """Ids of this phase's actionable (not done, not flagged) tasks, in file order."""
        return tuple(t.id for t in self.tasks if not t.done and not t.skippable)


def fence_bounds(lines: list[str]) -> tuple[int, int]:
    """Return the ``[start, end)`` line span *inside* the LOOP:QUEUE fence.

    Args:
        lines: Physical lines of the roadmap.
    Returns:
        Half-open span covering everything between the two fence markers.
    Raises:
        RoadmapCursorError: If either marker is missing or they are out of order.
    """
    starts = [i for i, line in enumerate(lines) if line.startswith(FENCE_START)]
    ends = [i for i, line in enumerate(lines) if line.startswith(FENCE_END)]
    if len(starts) != 1 or len(ends) != 1:
        raise RoadmapCursorError(
            f"expected exactly one {FENCE_START} and one {FENCE_END}; "
            f"found {len(starts)} and {len(ends)}",
            kind="fence",
        )
    if ends[0] <= starts[0]:
        raise RoadmapCursorError("LOOP:QUEUE end precedes start", kind="fence")
    return starts[0] + 1, ends[0]


def _block_end(lines: list[str], bullet: int, limit: int) -> int:
    """First line after ``bullet`` that opens a new block, capped at ``limit``."""
    for index in range(bullet + 1, limit):
        if BLOCK_END_RE.match(lines[index]):
            return index
    return limit


def _flags_for(lines: list[str], start: int, end: int) -> frozenset[str]:
    """Skip-flags found anywhere in a task's block body."""
    body = "".join(lines[start:end])
    found: set[str] = set()
    if ASK_GATE_RE.search(body):
        found.add(FLAG_ASK_GATE)
    if LIVE_RE.search(body):
        found.add(FLAG_LIVE)
    if DEFERRED_TOKEN in body:
        found.add(FLAG_DEFERRED)
    return frozenset(found)


def _parse_tasks(lines: list[str], phase_id: str, start: int, end: int) -> tuple[TaskEntry, ...]:
    """Parse every task bullet inside a phase's ``[start, end)`` span."""
    tasks: list[TaskEntry] = []
    for index in range(start, end):
        match = TASK_BULLET_RE.match(lines[index])
        if not match:
            continue
        block_end = _block_end(lines, index, end)
        tasks.append(
            TaskEntry(
                id=match.group(2),
                phase=phase_id,
                done=match.group(1).lower() == "x",
                flags=_flags_for(lines, index, block_end),
                start=index,
                end=block_end,
            )
        )
    return tuple(tasks)


def parse_roadmap(lines: list[str]) -> tuple[PhaseEntry, ...]:
    """Parse every phase and its tasks from inside the fence, in file order."""
    low, high = fence_bounds(lines)
    heads = [
        (i, PHASE_HEADING_RE.match(lines[i]).group(1))  # type: ignore[union-attr]
        for i in range(low, high)
        if PHASE_HEADING_RE.match(lines[i])
    ]
    phases: list[PhaseEntry] = []
    for position, (start, phase_id) in enumerate(heads):
        end = heads[position + 1][0] if position + 1 < len(heads) else high
        phases.append(
            PhaseEntry(
                id=phase_id,
                start=start,
                end=end,
                tasks=_parse_tasks(lines, phase_id, start, end),
            )
        )
    return tuple(phases)


def compute_next(
    phases: tuple[PhaseEntry, ...],
    *,
    after: str | None = None,
    exclude: frozenset[str] = frozenset(),
) -> tuple[PhaseEntry, TaskEntry] | None:
    """First actionable ``(phase, task)`` pair in file order, else ``None``.

    Flagged tasks (ask-gate, live, deferred) are never returned: an unattended session
    must not guess at a human decision, and skipping costs nothing where attempting
    costs a whole session. ``after`` resumes forward from a phase the loop is skipping;
    ``exclude`` drops already-skipped phase ids so they cannot be re-selected.

    Args:
        phases: Parsed phases, file order.
        after: Only consider this phase id and later ones.
        exclude: Phase ids to ignore entirely.
    Returns:
        The next actionable pair, or ``None`` when the queue is drained.
    """
    order = [p.id for p in phases]
    floor = order.index(after) if after in order else 0
    for position, phase in enumerate(phases):
        if position < floor or phase.id in exclude:
            continue
        for task in phase.tasks:
            if not task.done and not task.skippable:
                return phase, task
    return None


def slice_range(phases: tuple[PhaseEntry, ...], phase_id: str) -> tuple[int, int]:
    """The ``[start, end)`` line span of one phase; error if absent or duplicated."""
    matches = [p for p in phases if p.id == phase_id]
    if not matches:
        raise RoadmapCursorError(f"Phase {phase_id} not found.", kind="not_found")
    if len(matches) > 1:
        raise RoadmapCursorError(f"Phase {phase_id} is duplicated.", kind="duplicate")
    return matches[0].start, matches[0].end


def find_task(phases: tuple[PhaseEntry, ...], task_id: str) -> TaskEntry:
    """Locate a task by id; error if absent or duplicated."""
    matches = [t for p in phases for t in p.tasks if t.id == task_id]
    if not matches:
        raise RoadmapCursorError(f"Task {task_id} not found.", kind="not_found")
    if len(matches) > 1:
        raise RoadmapCursorError(f"Task {task_id} is duplicated.", kind="duplicate")
    return matches[0]


def _last_content_line(lines: list[str], start: int, end: int) -> int:
    """Index of the last non-blank line in ``[start, end)`` — where the marker lands."""
    for index in range(end - 1, start - 1, -1):
        if lines[index].strip():
            return index
    return start


def _append_marker(line: str, marker: str) -> str:
    """Append ``marker`` before the line's trailing newline, preserving CRLF."""
    for ending in ("\r\n", "\n"):
        if line.endswith(ending):
            return f"{line[: -len(ending)]}{marker}{ending}"
    return f"{line}{marker}"


def render_marked(
    lines: list[str], task: TaskEntry, date: str, unverified: str | None = None
) -> list[str]:
    """Return new lines with ``task``'s checkbox ticked and an audit marker appended.

    Two edits, both inside the task's own block: the ``- [ ]`` becomes ``- [x]`` (the
    authoritative done signal) and a provenance marker is appended to the block's last
    content line. When the task's own gate was red the marker records it as UNVERIFIED
    rather than hiding the debt.

    Args:
        lines: Physical roadmap lines.
        task: The task to mark.
        date: ISO date for the marker.
        unverified: Reason string when the gate was red, else None.
    Returns:
        A new list of lines; the input is not mutated.
    Raises:
        RoadmapCursorError: If the task's bullet line is not an unticked checkbox.
    """
    updated = list(lines)
    bullet = updated[task.start]
    if UNCHECKED_BOX not in bullet:
        raise RoadmapCursorError(f"Task {task.id} is not an open checkbox.", kind="not_open")
    updated[task.start] = bullet.replace(UNCHECKED_BOX, CHECKED_BOX, 1)
    template = UNVERIFIED_TEMPLATE if unverified else MARKER_TEMPLATE
    marker = template.format(task_id=task.id, reason=unverified, date=date)
    target = _last_content_line(updated, task.start, task.end)
    updated[target] = _append_marker(updated[target], marker)
    return updated


def verify(phases: tuple[PhaseEntry, ...], lines: list[str]) -> list[str]:
    """Return every structural finding (empty list means the queue is well-formed)."""
    findings: list[str] = []
    low, high = fence_bounds(lines)
    if not phases:
        findings.append("queue: no '### Phase' headings inside the LOOP:QUEUE fence")
    first_phase = phases[0].start if phases else high
    for index in range(low, first_phase):
        if TASK_BULLET_RE.match(lines[index]):
            findings.append(f"line {index + 1}: task bullet precedes any '### Phase' heading")
    for index in range(low, high):
        line = lines[index]
        if line.startswith(PHASE_HEADING_PREFIX) and not PHASE_HEADING_RE.match(line):
            findings.append(f"line {index + 1}: unparseable phase heading: {line.strip()}")
    seen_phases: set[str] = set()
    seen_tasks: set[str] = set()
    for phase in phases:
        if phase.id in seen_phases:
            findings.append(f"phase {phase.id}: duplicate phase id")
        seen_phases.add(phase.id)
        if not phase.tasks:
            findings.append(f"phase {phase.id}: no tasks")
        for task in phase.tasks:
            if task.id in seen_tasks:
                findings.append(f"task {task.id}: duplicate task id")
            seen_tasks.add(task.id)
    return findings
