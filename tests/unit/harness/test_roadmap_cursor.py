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
    "T13.1": ["deferred"],
    "T13.2": ["deferred"],
}


# The fence's phase ids, in file order. EVAL-P22B is a real phase, not a typo: it was
# inserted 2026-08-18 between EVAL-P22 and EVAL-P23 as the engine-iteration track
# (A/B pipeline unblocking), deliberately lettered so it could be added without
# renumbering P23/P24 and invalidating every cross-reference in the programme.
# Both assertions below were left pinning a bare contiguous P0..P24 when it landed,
# so they were red from that date until 2026-08-20 — hidden the whole time behind the
# `lint` failure that short-circuits `make check` before test-cov (ISSUE-189). Update
# this list deliberately, exactly as the tripwire docstring below asks.
# 2026-08-28 (DEC-233): the EVAL-P sequence is gone. The eval program was culled to a
# minimal trustworthy instrument (DEC-228) and ROADMAP.md was rebuilt around the 2026-08
# remediation program, archived at archive/ROADMAP_pre-remediation_2026-08-28.md. The
# fence now spans the four phases the overnight loop is allowed to own; R5/R6/R7 sit
# outside it deliberately (R6 would have the loop rewrite its own driver mid-run).
# File order is dependency order, which is why R4 precedes R3.
# 2026-09-03: the remediation program is complete and archived at
# archive/ROADMAP_remediation-2026-08_2026-09-03.md. The fence now spans the mechanical
# half of the M program — M1 (graph integrity) and M2 (the four unmeasured dimensions).
# M3, M4 and R6 sit outside it deliberately: M3 and M4 need human judgment and live model
# runs, and R6 would still have the loop rewrite its own driver mid-run.
# 2026-09-08: the M programme is retired and archived at
# archive/ROADMAP_M-programme_2026-09-08.md, and the fence now spans Sprints 1-8 of the
# T programme (Trim), phases T1..T16. Sprint 0 (T0, T0B) sits outside it deliberately — it
# rewrites the loop's own driver and skill — as do Sprints 9 and 10, which need human
# judgement and live model runs. This constant was left pinning M1/M2 by the commit that
# wrote the T roadmap, so `make check` was red from then until this update (T0.0).
_EXPECTED_PHASE_IDS: list[str] = [f"T{n}" for n in range(1, 17)]


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
        "Update the constant deliberately — see the tripwire docstring below."
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

    State 2026-08-10 (DEC-163): the fence was narrowed to **EVAL-P0..EVAL-P19**. The end
    marker moved from below EVAL-P24.3 to immediately above "### Phase EVAL-P20", on the
    same principle as the DEC-153 §3 narrowing described above: EVAL-P15..P19 recompute
    and repair over the artifact already on disk and can be validated against it, while
    EVAL-P20..P24 assume a post-regeneration artifact that does not exist, so the loop
    could only build them against fixtures. That is not hypothetical — it is how
    EVAL-P8.2's ``compare`` shipped green and then printed "Intersection: 0 cases /
    NO_DETECTABLE_CHANGE / p=1.0000" with exit 0 against the two real generation dirs.

    Current state (2026-08-15, DEC-178): the fence spans **EVAL-P0..EVAL-P24** again —
    reopened by **explicit human override**, not because DEC-163's three reopen
    conditions were met. They were not: ``EVAL-P17.6``'s live ``make check-conservation``
    still exits non-zero, and ``EVAL-P20.0`` measured 62.5% reproduction against the
    required ≥95% (DEC-176). ``EVAL-P20.0`` is ticked in ROADMAP.md as the record of that
    override, not as a claim its gate passed. This override does **not** fabricate
    completion of any other task — every phase's own ``HUMAN GATE`` blocks (H4, H6, H7,
    H8, H9, H10, H12) still gate their tasks on real, unticked-until-genuinely-done work,
    so ``compute_next`` below still returns real pending tasks, not free passes. Reopen
    conditions and the override record are at the marker in ROADMAP.md; the ordered
    human-side sequence is in project-harness/HUMAN_TASKS.md.

    Prior state (2026-08-09, DEC-160): the fence spanned EVAL-P0..EVAL-P24 — Program 1
    (P0..P8, precision), Program 2 (P9..P14, validity + the portfolio artifact, released
    2026-08-07), and Program 3 (P15..P24, the measurement apparatus, released 2026-08-09
    once `loop_gates.FROZEN_PATH_PREFIXES` covered `evals/calibration/` and
    `evals/generations/` so no unattended session can write the 393 human labels). The
    2026-08-15 reopening lands at the same span for a different reason (override, not
    conditions met) — see DEC-178, not DEC-160, for why.

    That release is why this test was red on the nights of 2026-08-09: DEC-160 moved the
    marker and verified the *cursor* (`roadmap-verify` OK, 25 phases) but not the tests
    that snapshot it, so the phase gate halted after EVAL-P11 and again after EVAL-P12 on
    a stale literal rather than a regression. The span assertion below is the snapshot;
    updating it is the deliberate act the docstring asks for.

    **What this pins, and why it no longer pins the pending list.** Earlier revisions
    asserted ``pending == 13``, then ``== 11``, then an exact id list, and were red every
    time (ISSUE-136). That is structural, not carelessness: *pending shrinks by one every
    time the loop succeeds*, so pinning it means the gate turns red on the first completed
    task of every night and stays red, which is exactly what happened across EVAL-P2..P5 —
    four phases committed under "pre-existing red gate" where a genuine regression would
    have looked identical. A tripwire that fires on success is not a tripwire.

    So this now pins the two things that should only change by deliberate human edit:

    * **the phase span** — a fence move is a conscious act, and P0..P24 must stay
      contiguous or ``compute_next`` silently skips a programme;
    * **the flagged set** — the loop refuses flagged tasks, so an accidental flag hides
      work forever and an accidental unflag hands a human decision to a 3am session.

    Pending is asserted only structurally (non-empty, and every id belongs to a phase in
    the fence), which catches a corrupted queue without firing on progress.

    **The flagged set is asserted by containment, not equality (ISSUE-136).** Equality had
    the same defect the pending list had, one step removed: a flagged task is skipped by
    the loop but still *ticked by a human session*, and the moment it is, it leaves the
    pending set and the literal dict is stale — EVAL-P6.4 did exactly that and is why this
    dict no longer names it. Both failure directions are still caught, without firing on
    progress:

    * an **accidental flag** (ISSUE-134: EVAL-P1.2's body said "Not an ask-gate" and the
      skip-regex matched the literal token through the negation) fails the subset check,
      because the new id is not in ``EXPECTED_FLAGS``;
    * an **accidental unflag** fails the second check, because a task still listed in
      ``EXPECTED_FLAGS`` and still pending must still carry exactly its recorded flags.

    Ticking a flagged task drops it from ``pending`` and is silently fine, which is the
    only behaviour equality got wrong.

    EVAL-P1.2 was flagged until 2026-08-07 **by accident**: its body contained the phrase
    "Not an ask-gate", and the cursor's skip-regex matches that literal token regardless
    of the negation around it, so the loop skipped the task for a reason that stated the
    opposite of what was meant (ISSUE-134). That is precisely the failure the flagged-set
    assertion below exists to catch.
    """
    phases, _ = _real_roadmap_phases()
    # 2026-08-15 (DEC-178): widened 20 -> 25 again. The fence end marker moved back below
    # EVAL-P24.3 by explicit human override — not because DEC-163's reopen conditions were
    # met (they were not; see the docstring above and DEC-178). This assertion firing on
    # that move is the tripwire working as designed.
    assert [p.id for p in phases] == _EXPECTED_PHASE_IDS

    # 2026-08-28 (DEC-233): no remediation phase is complete yet, so there is no
    # monotonic done-set to pin. Assert the structural invariant instead — every phase
    # in the fence has at least one task, which is what makes `is_done` meaningful
    # (a phase with zero tasks is never done and silently stalls compute_next).
    for phase in phases:
        assert phase.tasks, f"{phase.id} parsed to zero tasks"

    # Filter on `not done` the way the loop does: EVAL-P0.1/P0.3/P0.4 are *also*
    # skippable (their bodies still carry the ask-gate / live markers that gated
    # them) but they are ticked, so the loop is not being held back on them.
    flagged = {t.id: sorted(t.flags) for p in phases for t in p.tasks if t.skippable and not t.done}

    # No task may acquire a flag that is not recorded here (ISSUE-134).
    unexpected = {task_id: got for task_id, got in flagged.items() if task_id not in EXPECTED_FLAGS}
    assert not unexpected, (
        f"tasks newly skipped by the loop, with no recorded reason: {unexpected}. "
        "If deliberate, add them to EXPECTED_FLAGS; if not, the skip-regex matched prose."
    )

    # No still-pending task may quietly lose or change its flag.
    for task_id, expected in EXPECTED_FLAGS.items():
        if task_id in flagged:
            assert flagged[task_id] == expected, (
                f"{task_id} flags changed: expected {expected}, got {flagged[task_id]}"
            )

    # Structural only — pending shrinks on every success and must not fire this gate.
    known_task_ids = {t.id for p in phases for t in p.tasks}
    pending = [task_id for p in phases for task_id in p.pending]
    # 2026-09-02 (DEC-252): `assert pending` replaced by an equivalence, because BOTH of
    # its predecessors fired on a correct queue and this one now has too.
    #
    # The history is the argument. `assert pending == []` was right while the EVAL queue
    # was honestly drained and wrong the moment the remediation queue was loaded full.
    # DEC-233 flipped it to `assert pending` — right for a full queue, and wrong the moment
    # the remediation programme finished, which is today: R0–R4 are complete and the only
    # unticked task in the fence is R1.7, a flagged ask-gate. Each version pinned a
    # snapshot of how much work happened to be left, so each was guaranteed to go red on
    # a legitimate state change. That is a tripwire that fires on success, which the
    # docstring above already names as the thing to avoid.
    #
    # The invariant that holds in EVERY state is that `pending` is exactly the tasks the
    # loop can act on: unticked and unflagged. It catches the 2026-08-28 corruption —
    # a full file parsing to ALL_DONE leaves actionable tasks missing from `pending`, so
    # the two sides diverge — while permitting both an honestly full and an honestly
    # drained queue, and it shrinks in step with progress rather than against it.
    actionable = sorted(t.id for p in phases for t in p.tasks if not t.done and not t.skippable)
    assert sorted(pending) == actionable, (
        "pending diverged from the tasks the loop can act on. Missing ids mean the queue "
        "parsed to less than the file holds — the silent no-op that made the misplaced "
        "fence look like 'queue drained' on 2026-08-28. Extra ids mean the reverse."
    )
    assert set(pending) <= known_task_ids


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
