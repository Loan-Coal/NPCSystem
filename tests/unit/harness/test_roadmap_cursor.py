"""Regression tests for the overnight loop's roadmap cursor.

The three that matter most, each guarding a way an unattended night is lost silently:

* **CRLF preservation** — a ``--mark`` that rewrites all 1183 lines LF turns every task
  commit into a whole-file diff and destroys "the commit is the transaction".
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
    assert ids == [f"EVAL-P{n}" for n in range(len(ids))], (
        f"queue must be a contiguous EVAL-P prefix starting at P0, got {ids}"
    )


def test_real_roadmap_fence_state_tripwire() -> None:
    """Snapshot of the *current* fence, so a move is a conscious act.

    UPDATE DELIBERATELY when the fence moves, and only alongside the ROADMAP
    reopen condition.

    History. 2026-08-02 (DEC-153 §3) narrowed the fence to EVAL-P0 because
    ``compute_next`` skips flagged tasks without blocking, so a wider fence let the
    loop drain EVAL-P1..P7 while EVAL-P0.3 (ask-gate) and EVAL-P0.4 (the live
    measured baseline every later estimate depends on) sat unchecked forever —
    finishing the program having measured nothing. That narrowing worked: the
    baseline was measured on 2026-08-06 before a judge call was spent on P1..P8.

    Current state (2026-08-07): the fence spans EVAL-P0..EVAL-P14 — Program 1
    (P0..P8, precision) plus Program 2 (P9..P14, validity + the portfolio artifact),
    released to the loop on 2026-08-07.

    **What this pins, and why it no longer pins the pending list.** Earlier revisions
    asserted ``pending == 13``, then ``== 11``, then an exact id list, and were red every
    time (ISSUE-136). That is structural, not carelessness: *pending shrinks by one every
    time the loop succeeds*, so pinning it means the gate turns red on the first completed
    task of every night and stays red, which is exactly what happened across EVAL-P2..P5 —
    four phases committed under "pre-existing red gate" where a genuine regression would
    have looked identical. A tripwire that fires on success is not a tripwire.

    So this now pins the two things that should only change by deliberate human edit:

    * **the phase span** — a fence move is a conscious act, and P0..P14 must stay
      contiguous or ``compute_next`` silently skips a programme;
    * **the flagged set** — the loop refuses flagged tasks, so an accidental flag hides
      work forever and an accidental unflag hands a human decision to a 3am session.

    Pending is asserted only structurally (non-empty, and every id belongs to a phase in
    the fence), which catches a corrupted queue without firing on progress.

    EVAL-P1.2 was flagged until 2026-08-07 **by accident**: its body contained the phrase
    "Not an ask-gate", and the cursor's skip-regex matches that literal token regardless
    of the negation around it, so the loop skipped the task for a reason that stated the
    opposite of what was meant (ISSUE-134). That is precisely the failure the flagged-set
    assertion below exists to catch.
    """
    phases, _ = _real_roadmap_phases()
    assert [p.id for p in phases] == [f"EVAL-P{n}" for n in range(15)]

    # Program 1's foundation phases are complete: nothing actionable, nothing held back.
    for phase_id in ("EVAL-P0", "EVAL-P1", "EVAL-P2", "EVAL-P3", "EVAL-P4"):
        phase = next(p for p in phases if p.id == phase_id)
        assert phase.pending == (), f"{phase_id} regained a pending task"
        assert phase.is_done, f"{phase_id} is no longer done"

    # Filter on `not done` the way the loop does: EVAL-P0.1/P0.3/P0.4 are *also*
    # skippable (their bodies still carry the ask-gate / live markers that gated
    # them) but they are ticked, so the loop is not being held back on them.
    flagged = {t.id: sorted(t.flags) for p in phases for t in p.tasks if t.skippable and not t.done}
    assert flagged == {
        # Need a running engine + Neo4j + Ollama.
        "EVAL-P6.4": ["live"],
        "EVAL-P8.3": ["live"],
        "EVAL-P9.3": ["live"],
        "EVAL-P12.1": ["live"],
        "EVAL-P12.4": ["live"],
        # Inputs do not exist yet: no adjudicated labels, no published run artifact.
        "EVAL-P11.2": ["deferred"],
        "EVAL-P11.3": ["deferred"],
        "EVAL-P13.2": ["deferred"],
        "EVAL-P13.3": ["deferred"],
        "EVAL-P14.3": ["deferred"],
    }

    # Structural only — pending shrinks on every success and must not fire this gate.
    known_task_ids = {t.id for p in phases for t in p.tasks}
    pending = [task_id for p in phases for task_id in p.pending]
    assert pending, "queue drained — move the fence or the programme is over"
    assert set(pending) <= known_task_ids


def test_real_roadmap_is_entirely_crlf() -> None:
    """ROADMAP.md must stay 100% CRLF, or a one-line ``--mark`` becomes a whole-file diff.

    ``roadmap_cursor`` reads and writes with ``newline=""`` precisely so each line keeps
    its original terminator; the property that makes "the commit is the transaction" hold
    is that every line already agrees. Any tool that rewrites the file through Python's
    universal-newline handling silently converts all 1500+ lines to LF, and the next
    ``--mark`` then produces a diff touching the whole file instead of one checkbox.
    That happened on 2026-08-07 and was only caught by inspection — hence this guard.
    """
    path = Path(__file__).resolve().parents[3] / "project-harness" / "ROADMAP.md"
    raw = path.read_bytes()
    total_lf = raw.count(b"\n")
    crlf = raw.count(b"\r\n")

    assert total_lf > 0, "roadmap is empty"
    assert crlf == total_lf, f"{total_lf - crlf} lines are bare LF; roadmap must be all CRLF"


def test_real_roadmap_end_marker_is_not_repeated_inside_the_queue() -> None:
    """A second ``end`` token between the markers would silently truncate the queue.

    The narrowed fence put P0.4's body next to the marker it talks about, so the
    prose was one backtick-quoted token away from cutting the queue short.
    """
    _, lines = _real_roadmap_phases()
    start, end = fence_bounds(lines)
    inner = "".join(lines[start:end])
    assert "LOOP:QUEUE end" not in inner
