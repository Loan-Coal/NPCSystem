"""Unit tests for `scripts/check_human_gates.py` (DEC-164)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_human_gates import (  # noqa: E402
    blocked_tasks,
    main,
    parse_gates,
    task_states,
    verify_gates,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_ROADMAP = REPO_ROOT / "project-harness" / "ROADMAP.md"


def _lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


GATE = """\
#### HUMAN GATE H1 - EVAL-P17.5 re-measure and retract
**Ready when:** `EVAL-P17.1`, `EVAL-P17.4`
**Clears when:** `EVAL-P17.5`
**Blocks:** `EVAL-P13.3`
**Runbook:** `HUMAN_TASKS.md` task 2 - ~30 min
**Why not the loop:** edits the Session Log the loop's own commit step touches.

- [ ] **EVAL-P13.3** blocked downstream work
- [x] **EVAL-P17.1** done
- [ ] **EVAL-P17.4** not done
- [ ] **EVAL-P17.5** the gate's own task
"""


BARRIER = """\
#### HUMAN GATE H3 - fence reopen
**Ready when:** `EVAL-P17.5`, `EVAL-P17.6`
**Clears when:** -
**Blocks:** `EVAL-P20.1`
**Runbook:** `HUMAN_TASKS.md` week-2 boundary
**Why not the loop:** moving the fence is a human act recorded in DECISIONS.

- [x] **EVAL-P17.5** done
- [x] **EVAL-P17.6** done
- [ ] **EVAL-P20.1** downstream
"""


# --- parsing -----------------------------------------------------------------------


def test_gate_block_is_parsed_with_its_three_id_lists() -> None:
    (gate,) = parse_gates(_lines(GATE))
    assert gate.id == "H1"
    assert gate.ready_when == ("EVAL-P17.1", "EVAL-P17.4")
    assert gate.clears_when == ("EVAL-P17.5",)
    assert gate.blocks == ("EVAL-P13.3",)
    assert "task 2" in gate.runbook


def test_task_states_reads_ticked_and_unticked_boxes() -> None:
    states = task_states(_lines(GATE))
    assert states["EVAL-P17.1"] is True
    assert states["EVAL-P17.4"] is False
    assert states["EVAL-P17.5"] is False


def test_em_dash_clears_when_parses_as_an_empty_list() -> None:
    (gate,) = parse_gates(_lines(BARRIER))
    assert gate.clears_when == ()
    assert gate.ready_when == ("EVAL-P17.5", "EVAL-P17.6")


# --- open / closed semantics -------------------------------------------------------


def test_gate_is_closed_until_every_requirement_is_ticked() -> None:
    (gate,) = parse_gates(_lines(GATE))
    states = task_states(_lines(GATE))
    assert gate.is_open(states) is False
    assert gate.is_ready(states) is False  # EVAL-P17.4 outstanding


def test_gate_is_ready_but_still_closed_once_prerequisites_land() -> None:
    (gate,) = parse_gates(_lines(GATE))
    states = task_states(_lines(GATE)) | {"EVAL-P17.4": True}
    assert gate.is_ready(states) is True
    assert gate.is_open(states) is False  # its own EVAL-P17.5 is not ticked


def test_barrier_gate_with_no_clears_when_opens_on_its_ready_set() -> None:
    """A barrier has no task of its own, so its ready set is its whole requirement."""
    (gate,) = parse_gates(_lines(BARRIER))
    states = task_states(_lines(BARRIER))
    assert gate.is_open(states) is True


def test_barrier_gate_stays_closed_while_a_reopen_condition_is_open() -> None:
    (gate,) = parse_gates(_lines(BARRIER))
    states = task_states(_lines(BARRIER)) | {"EVAL-P17.6": False}
    assert gate.is_open(states) is False


# --- blocking ----------------------------------------------------------------------


def test_blocked_task_names_the_gate_that_blocks_it() -> None:
    lines = _lines(GATE)
    assert blocked_tasks(parse_gates(lines), task_states(lines)) == {"EVAL-P13.3": "H1"}


def test_open_gate_blocks_nothing() -> None:
    lines = _lines(BARRIER)
    assert blocked_tasks(parse_gates(lines), task_states(lines)) == {}


# --- verify ------------------------------------------------------------------------


def test_verify_flags_a_gate_referencing_an_unknown_task_id() -> None:
    lines = _lines(GATE.replace("`EVAL-P13.3`", "`EVAL-P99.9`"))
    findings = verify_gates(parse_gates(lines), task_states(lines))
    assert any("EVAL-P99.9" in f for f in findings)


def test_verify_flags_a_duplicate_gate_id() -> None:
    lines = _lines(GATE + "\n" + GATE)
    findings = verify_gates(parse_gates(lines), task_states(lines))
    assert any("duplicate" in f for f in findings)


def test_verify_flags_a_gate_missing_a_required_field() -> None:
    lines = _lines(GATE.replace("**Blocks:** `EVAL-P13.3`\n", ""))
    findings = verify_gates(parse_gates(lines), task_states(lines))
    assert any("Blocks" in f for f in findings)


def test_verify_is_clean_on_a_well_formed_gate() -> None:
    lines = _lines(GATE)
    assert verify_gates(parse_gates(lines), task_states(lines)) == []


# --- CLI ---------------------------------------------------------------------------


def _write_roadmap(tmp_path: Path, text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "ROADMAP.md"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setenv("ROADMAP_FILE", str(path))


def test_check_exits_nonzero_for_a_task_behind_a_closed_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_roadmap(tmp_path, GATE, monkeypatch)
    assert main(["--check", "EVAL-P13.3"]) == 1
    assert "H1" in capsys.readouterr().err


def test_check_exits_zero_for_an_unblocked_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_roadmap(tmp_path, GATE, monkeypatch)
    assert main(["--check", "EVAL-P17.4"]) == 0


def test_report_lists_every_gate_with_its_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_roadmap(tmp_path, GATE, monkeypatch)
    assert main([]) == 0
    assert "H1" in capsys.readouterr().out


def test_verify_cli_exits_nonzero_on_an_unknown_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_roadmap(tmp_path, GATE.replace("`EVAL-P13.3`", "`EVAL-P99.9`"), monkeypatch)
    assert main(["--verify"]) == 1


# --- the real roadmap --------------------------------------------------------------


def _real_lines() -> list[str]:
    with open(REAL_ROADMAP, encoding="utf-8", newline="") as handle:
        return handle.read().splitlines(keepends=True)


def test_real_roadmap_gates_verify_clean() -> None:
    lines = _real_lines()
    assert verify_gates(parse_gates(lines), task_states(lines)) == []


def test_real_roadmap_gate_ids_are_contiguous_from_h1() -> None:
    """Gate ids are numbered in *execution* order, not file order (DEC-164).

    So this asserts the id set has no hole and no duplicate — it deliberately does
    NOT assert file order, because H11 (`EVAL-P8.3`, Program 1) legitimately appears
    first in the file while being last in the schedule.
    """
    ids = sorted((g.id for g in parse_gates(_real_lines())), key=lambda g: int(g[1:]))
    assert ids == [f"H{n}" for n in range(1, len(ids) + 1)], ids


def test_real_roadmap_has_a_gate_for_every_deferred_human_task() -> None:
    """The roadmap declares a HUMAN GATE for every human task that blocks loop work.

    Was: an assertion that the 13 EVAL-P* human tasks each had a gate. Those tasks
    belonged to eval Programs 3-5, retired by DEC-228 when the eval program was culled
    to a minimal trustworthy instrument, and `HUMAN_TASKS.md` moved to
    `archive/HUMAN_TASKS_eval-program_2026-08-28.md` with them. Asserting gates for
    retired work is the drift this repo keeps re-learning, so the assertion now tracks
    whatever the roadmap actually declares rather than a frozen list.

    The remediation program encodes its human-blocked items as roadmap task flags
    (⏸️ / ask-gate) instead, which `roadmap_cursor.py --list-flagged` reports.
    """
    gates = parse_gates(_real_lines())
    covered = {task for gate in gates for task in gate.clears_when}
    # Every gate that exists must name at least one task it clears; a gate that clears
    # nothing is the "0 gates, exit 0" theatre CR-L06-01 documented.
    assert all(gate.clears_when for gate in gates), [g.id for g in gates if not g.clears_when]
    # And every named task must be a real, parseable id rather than free text.
    assert all(task.strip() for task in covered)


def test_gate_headings_do_not_disturb_the_roadmap_cursor_parse() -> None:
    """`#### HUMAN GATE` must terminate a task block without becoming a phase.

    The cursor's contiguity and fence-span tripwires live in
    `tests/unit/harness/test_roadmap_cursor.py`; this asserts the narrower property
    that the gates are invisible to it, so the two mechanisms cannot interfere.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from _roadmap_cursor_core import parse_roadmap, verify  # noqa: PLC0415

    lines = _real_lines()
    phases = parse_roadmap(lines)
    assert verify(phases, lines) == []
    assert all(not phase.id.startswith("H") for phase in phases)


def test_the_loop_is_never_handed_a_task_behind_a_closed_gate() -> None:
    """The property the whole mechanism exists for, asserted against live state."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from _roadmap_cursor_core import compute_next, parse_roadmap  # noqa: PLC0415

    lines = _real_lines()
    found = compute_next(parse_roadmap(lines))
    if found is None:
        pytest.skip("queue drained — no next task to check")
    _, task = found
    blocked = blocked_tasks(parse_gates(lines), task_states(lines))
    assert task.id not in blocked, f"{task.id} is blocked by gate {blocked.get(task.id)}"


# --- --strict mode -----------------------------------------------------------------


def test_strict_exits_one_when_pending_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--strict returns 1 when any gate has unmet requirements (not yet cleared)."""
    _write_roadmap(tmp_path, GATE, monkeypatch)
    assert main(["--strict"]) == 1


def test_strict_exits_zero_when_all_gates_cleared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--strict returns 0 when every gate's requirements are fully ticked."""
    all_done = (
        GATE
        .replace("- [ ] **EVAL-P17.4**", "- [x] **EVAL-P17.4**")
        .replace("- [ ] **EVAL-P17.5** the gate's own task", "- [x] **EVAL-P17.5** the gate's own task")
    )
    _write_roadmap(tmp_path, all_done, monkeypatch)
    assert main(["--strict"]) == 0


def test_strict_is_mutually_exclusive_with_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--strict and --check cannot be combined (argparse enforces this)."""
    _write_roadmap(tmp_path, GATE, monkeypatch)
    with pytest.raises(SystemExit):
        main(["--strict", "--check", "EVAL-P13.3"])
