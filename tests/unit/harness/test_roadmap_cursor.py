"""Regression tests for the overnight loop's roadmap cursor.

The three that matter most, each guarding a way an unattended night is lost silently:

* **Terminator preservation** — a ``--mark`` that rewrites every line to the other
  terminator turns each task commit into a whole-file diff and destroys "the commit is
  the transaction". The synthetic fixture below stays CRLF on purpose: the writer must
  preserve what it is given, not impose the repo's current convention.
* **Fence isolation** — 19 open tasks live outside the queue (Phase PERF, bullets inside
  "## Completed", Parked). If the cursor ever sees them, the loop starts one at 3am.
* **✅-in-prose** — this roadmap writes "DEC-147 ✅ ACCEPTED" in task bodies. The upstream
  kit keys done off a ✅ token, which here would mark open tasks done on sight.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from _roadmap_cursor_core import (  # noqa: E402
    FENCE_END,
    RoadmapCursorError,
    compute_next,
    fence_bounds,
    find_task,
    parse_roadmap,
    render_marked,
    verify,
)

FENCED = (
    "# Roadmap\r\n"
    "- [ ] **OUTSIDE.1** must never be seen\r\n"
    "<!-- LOOP:QUEUE start -->\r\n"
    "### Phase EVAL-P0 — Foundations\r\n"
    "- [x] **EVAL-P0.1** already done\r\n"
    "- [ ] **EVAL-P0.2** real work here\r\n"
    "      Files: create evals/adapter.py\r\n"
    "      Note: DEC-147 ✅ ACCEPTED 2026-07-31 (prose, not a done marker)\r\n"
    "- [ ] **EVAL-P0.3** gated work\r\n"
    "      ⚠️ **ask-gate:** edits the shared make check gate.\r\n"
    "### Phase EVAL-P1 — Schema\r\n"
    "- [ ] **EVAL-P1.1** more work\r\n"
    "<!-- LOOP:QUEUE end -->\r\n"
    "- [ ] **TRAP.1** also never seen\r\n"
)


def _lines(text: str = FENCED) -> list[str]:
    return text.splitlines(keepends=True)


def test_fence_hides_tasks_outside_the_queue() -> None:
    ids = {t.id for p in parse_roadmap(_lines()) for t in p.tasks}
    assert ids == {"EVAL-P0.1", "EVAL-P0.2", "EVAL-P0.3", "EVAL-P1.1"}
    assert "OUTSIDE.1" not in ids and "TRAP.1" not in ids


def test_checkmark_in_prose_does_not_mark_a_task_done() -> None:
    task = find_task(parse_roadmap(_lines()), "EVAL-P0.2")
    assert task.done is False


def test_compute_next_skips_flagged_tasks() -> None:
    phase, task = compute_next(parse_roadmap(_lines()))
    assert (phase.id, task.id) == ("EVAL-P0", "EVAL-P0.2")


def test_ask_gate_task_is_flagged_not_actionable() -> None:
    task = find_task(parse_roadmap(_lines()), "EVAL-P0.3")
    assert task.flags == frozenset({"ask-gate"})
    assert task.skippable is True


def test_next_after_resumes_forward_from_a_skipped_phase() -> None:
    phase, task = compute_next(parse_roadmap(_lines()), after="EVAL-P1")
    assert (phase.id, task.id) == ("EVAL-P1", "EVAL-P1.1")


def test_all_done_returns_none() -> None:
    text = FENCED.replace("- [ ] **EVAL-P0.2**", "- [x] **EVAL-P0.2**").replace(
        "- [ ] **EVAL-P1.1**", "- [x] **EVAL-P1.1**"
    )
    assert compute_next(parse_roadmap(_lines(text))) is None


def test_mark_preserves_crlf_and_touches_only_the_task_block() -> None:
    lines = _lines()
    task = find_task(parse_roadmap(lines), "EVAL-P0.2")
    marked = render_marked(lines, task, "2026-08-01")

    assert len(marked) == len(lines)
    assert all(line.endswith("\r\n") for line in marked)
    changed = [i for i, (a, b) in enumerate(zip(lines, marked)) if a != b]
    assert changed == [task.start, task.end - 1]
    assert "- [x] **EVAL-P0.2**" in marked[task.start]
    assert "✅ AUTO (EVAL-P0.2, 2026-08-01)" in marked[task.end - 1]


def test_mark_round_trips_back_as_done() -> None:
    lines = _lines()
    task = find_task(parse_roadmap(lines), "EVAL-P0.2")
    marked = render_marked(lines, task, "2026-08-01")
    assert find_task(parse_roadmap(marked), "EVAL-P0.2").done is True


def test_unverified_marker_records_the_reason() -> None:
    lines = _lines()
    task = find_task(parse_roadmap(lines), "EVAL-P0.2")
    marked = render_marked(lines, task, "2026-08-01", "gate-red")
    assert "⚠️ UNVERIFIED (EVAL-P0.2, gate-red, 2026-08-01)" in marked[task.end - 1]


def test_marking_an_already_ticked_task_is_refused() -> None:
    lines = _lines()
    task = find_task(parse_roadmap(lines), "EVAL-P0.1")
    with pytest.raises(RoadmapCursorError) as excinfo:
        render_marked(lines, task, "2026-08-01")
    assert excinfo.value.kind == "not_open"


@pytest.mark.parametrize(
    "text",
    ["# no fence at all\r\n", "<!-- LOOP:QUEUE start -->\r\n", FENCED + FENCED],
)
def test_missing_or_duplicated_fence_is_an_error(text: str) -> None:
    with pytest.raises(RoadmapCursorError) as excinfo:
        fence_bounds(_lines(text))
    assert excinfo.value.kind == "fence"


def test_verify_is_clean_on_a_well_formed_queue() -> None:
    lines = _lines()
    assert verify(parse_roadmap(lines), lines) == []


def test_verify_flags_a_task_bullet_before_any_phase_heading() -> None:
    text = FENCED.replace(
        "<!-- LOOP:QUEUE start -->\r\n",
        "<!-- LOOP:QUEUE start -->\r\n- [ ] **ORPHAN.1** no phase\r\n",
    )
    lines = _lines(text)
    findings = verify(parse_roadmap(lines), lines)
    assert any("precedes any" in f for f in findings)


def test_verify_flags_a_duplicate_task_id() -> None:
    text = FENCED.replace(
        "- [ ] **EVAL-P1.1** more work\r\n",
        "- [ ] **EVAL-P1.1** more work\r\n- [ ] **EVAL-P0.2** duplicate\r\n",
    )
    lines = _lines(text)
    assert any("duplicate task id" in f for f in verify(parse_roadmap(lines), lines))


def _real_roadmap_phases():
    path = Path(__file__).resolve().parents[3] / "project-harness" / "ROADMAP.md"
    with open(path, encoding="utf-8", newline="") as handle:
        lines = handle.read().splitlines(keepends=True)
    return parse_roadmap(lines), lines


# Every task the overnight loop is *expected* to refuse, with the reason it refuses it.
# Asserted by containment, not equality — see test_real_roadmap_fence_state_tripwire.
# A task listed here that is later ticked simply drops out of `pending`; leaving its entry
# behind is harmless, so this list is append-mostly and does not go stale on progress.
EXPECTED_FLAGS: dict[str, list[str]] = {
    # 2026-09-03: empty, and deliberately so. The R-phase entries left with the archived
    # remediation program. Every task now inside the fence (M1, M2) is mechanical, so
    # nothing in it should be skipped. The split is by nature: work needing a human
    # judgment or a live model run lives OUTSIDE the fence (M3, M4, R6), where the cursor
    # never sees it, rather than inside it behind a skip flag. An empty map still catches
    # a regression — any fence task that acquires a flag fails the `unexpected` check
    # below, which is exactly the ISSUE-134 trap of the skip-regex matching prose.
    # 2026-09-08: no longer empty. The M programme was retired and the fence moved to the
    # T programme (Sprints 1-8, T1..T16). Six fence tasks carry the pause glyph at their
    # heading because they need a running stack or a live measurement, and the owner chose
    # to keep them inside the fence — beside the work they verify — rather than outside it.
    # Each is recorded in ROADMAP.md's Deferred backlog with an owner and a due date, and
    # `make roadmap-audit` reports them, so skipping them is visible rather than silent.
    # 2026-09-17: narrowed to the census pair. The loop now rebuilds the isolated eval stack
    # for live checks (scripts/eval_stack_at.sh), so T3.3, T6.3, T7.4, T15.2, T16.1 and T16.4
    # — deferred only because the loop could not see live code — are loop work. T13.1 and
    # T13.2 stay flagged because a person plays the interactive walkthrough the census needs.
    # 2026-10-21 (DEC-297, DEC-322): empty again. Sprints 0-8 are archived and the drain
    # programme keeps every human-gated item OUTSIDE the fence ("Owner work"), so no fence
    # task may carry a flag; T13.1/T13.2 were replaced by the T23 demo-shrink deletion phase.
}


# The fence's current phase ids, in file order. Update deliberately.
# Full change history archived at project-harness/archive/ROADMAP_T-programme_2026-10-21.md
# and project-harness/archive/ROADMAP_M-programme_2026-09-08.md.
_EXPECTED_PHASE_IDS: list[str] = ["T21", "T22", "T23", "T24", "T25", "T26", "T28", "T17", "T19", "T29"]


def test_real_roadmap_parses_and_verifies_clean() -> None:
    """Structural invariant — holds no matter where the fence is placed.

    Deliberately does NOT pin the fence width: DEC-153 §3 makes moving the
    ``end`` marker a planned, recurring operation (narrow it so the loop cannot
    outrun a live measurement task, widen it once that task is ticked). A test
    that froze the width would fail on every intentional move and train whoever
    hits it to edit the number without reading why.
    """
    phases, lines = _real_roadmap_phases()
    assert verify(phases, lines) == []
    assert phases, "queue fence parsed to zero phases"
    ids = [p.id for p in phases]
    assert ids == _EXPECTED_PHASE_IDS, (
        f"queue phases changed: expected {_EXPECTED_PHASE_IDS}, got {ids}. "
        "Update the constant deliberately — see the history comment above _EXPECTED_PHASE_IDS."
    )
    for phase in phases:
        assert phase.tasks, f"{phase.id} parsed to zero tasks"
    pending = [task_id for p in phases for task_id in p.pending]
    actionable = sorted(t.id for p in phases for t in p.tasks if not t.done and not t.skippable)
    assert sorted(pending) == actionable, (
        "pending diverged from the tasks the loop can act on. Missing ids mean the queue "
        "parsed to less than the file holds — the silent no-op that made the misplaced "
        "fence look like 'queue drained' on 2026-08-28. Extra ids mean the reverse."
    )



def test_real_roadmap_line_endings_are_uniform() -> None:
    """ROADMAP.md must use one line terminator throughout, or ``--mark`` rewrites it whole.

    ``roadmap_cursor`` reads and writes with ``newline=""`` precisely so each line keeps
    its original terminator; the property that makes "the commit is the transaction" hold
    is that every line already agrees. Any tool that rewrites the file through Python's
    universal-newline handling silently converts all 1500+ lines, and the next ``--mark``
    then produces a diff touching the whole file instead of one checkbox. That happened on
    2026-08-07 and was only caught by inspection — hence this guard.

    Was ``test_real_roadmap_is_entirely_crlf`` until 2026-08-31. The roadmap was all-CRLF
    then because the repo had no line-ending policy; ``.gitattributes`` now stores and
    checks out every text file LF, so pinning CRLF would pin the state the policy removed.
    Uniformity was always the real invariant — CRLF was only which uniform state it
    happened to be in.
    """
    raw = (Path(__file__).resolve().parents[3] / "project-harness" / "ROADMAP.md").read_bytes()
    total_lf = raw.count(b"\n")
    crlf = raw.count(b"\r\n")

    assert total_lf > 0, "roadmap is empty"
    assert crlf in (0, total_lf), (
        f"{crlf} of {total_lf} lines are CRLF and the rest are LF — mixed terminators make "
        "the next --mark rewrite the whole file"
    )


def test_real_roadmap_end_marker_is_not_repeated_inside_the_queue() -> None:
    """A second ``end`` *line* between the markers would truncate or void the queue.

    The narrowed fence put P0.4's body next to the marker it talks about, so the
    prose was one backtick-quoted token away from cutting the queue short.

    Matched the way ``fence_bounds`` matches — ``line.startswith(FENCE_END)`` — rather
    than as a substring anywhere in the body. The substring form was red from 2026-08-09
    for a reason that was not a hazard: DEC-160 moved the marker below Program 3, which
    brought Program 3's own "Fence policy" paragraph *inside* the queue, and that
    paragraph quotes the marker in prose to explain itself. A rule that forbids the
    roadmap from discussing its own fence inside the fence costs a HALT and buys nothing,
    because a quoted token mid-line cannot truncate anything: ``fence_bounds`` only ever
    looks at line starts, and a genuine duplicate marker line raises
    ``RoadmapCursorError`` rather than silently cutting the queue. This asserts the real
    invariant, and the assertion below pins that failure mode explicitly.
    """
    _, lines = _real_roadmap_phases()
    start, end = fence_bounds(lines)
    repeated = [start + i for i, line in enumerate(lines[start:end]) if line.startswith(FENCE_END)]
    assert not repeated, f"a second fence-end marker opens lines {repeated} inside the queue"


def test_duplicate_end_marker_raises_rather_than_truncating() -> None:
    """The failure mode above is loud, not silent — pinned so it stays that way.

    ``fence_bounds`` could equally have taken ``ends[0]``, which would quietly drop every
    task after the first duplicate marker. It counts instead, so this must raise.
    """
    text = FENCED.replace(
        "- [ ] **EVAL-P1.1** more work\r\n",
        "<!-- LOOP:QUEUE end -->\r\n- [ ] **EVAL-P1.1** more work\r\n",
    )
    with pytest.raises(RoadmapCursorError):
        fence_bounds(_lines(text))
