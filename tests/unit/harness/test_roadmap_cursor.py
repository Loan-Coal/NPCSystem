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


def test_real_roadmap_parses_and_verifies_clean() -> None:
    path = Path(__file__).resolve().parents[3] / "project-harness" / "ROADMAP.md"
    with open(path, encoding="utf-8", newline="") as handle:
        lines = handle.read().splitlines(keepends=True)
    phases = parse_roadmap(lines)
    assert verify(phases, lines) == []
    assert [p.id for p in phases] == [f"EVAL-P{n}" for n in range(8)]
    actionable = sum(len(p.pending) for p in phases)
    assert actionable == 22
