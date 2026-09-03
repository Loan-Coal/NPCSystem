"""
Module: test_check_integration_baseline
Layer: test (unit)
Purpose: Pin the integration ratchet's three behaviours — a new failure reds, a resolved
         one only nags, and an all-skip run cannot pass green (R2.2).
Dependencies: pytest, pathlib; scripts/check_integration_baseline.py
Used by: pytest (make test / make check)

Why this exists: the gate's whole point is that CI stayed green for months over an
integration suite where 34 of 43 tests skipped. "Nothing failed" was never evidence the
suite ran, so the executed-count floor is as load-bearing as the failure comparison and is
asserted here alongside it.

Driven with synthetic pytest output — no Neo4j, no subprocess. A unit test that needed the
graph up would be an integration test, and would not run in `make check`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_integration_baseline import (  # noqa: E402
    MIN_EXECUTED_TESTS,
    evaluate,
    executed_count,
    failing_node_ids,
    load_baseline,
    write_baseline,
)

_NODE_A = "tests/integration/test_faction_integration.py::test_remove_controls_raises_when_no_edge"
_NODE_B = "tests/integration/test_reputation_integration.py::test_reputation_context_included_above_threshold"
_NODE_NEW = "tests/integration/test_tick_advance_integration.py::test_something_new"


def _run_output(failed: list[str], passed: int, skipped: int = 0) -> str:
    """Build pytest short-summary output with the given failures and counts."""
    lines = [f"FAILED {node} - AssertionError" for node in failed]
    tail = f"{len(failed)} failed, {passed} passed"
    if skipped:
        tail += f", {skipped} skipped"
    lines.append(f"{tail} in 109.10s (0:01:49)")
    return "\n".join(lines)


def test_a_new_failure_reds() -> None:
    """A node id absent from the allowlist is a regression."""
    output = _run_output([_NODE_A, _NODE_NEW], passed=41)
    assert evaluate(output, {_NODE_A, _NODE_B}) == 1


def test_the_new_failure_is_named(capsys) -> None:
    """The gate must say which test regressed, or it cannot be acted on."""
    evaluate(_run_output([_NODE_NEW], passed=42), {_NODE_A})
    assert _NODE_NEW in capsys.readouterr().out


def test_the_recorded_failures_pass() -> None:
    """Exactly the known-failing set is the steady state, not a failure."""
    output = _run_output([_NODE_A, _NODE_B], passed=41)
    assert evaluate(output, {_NODE_A, _NODE_B}) == 0


def test_a_resolved_failure_nags_but_does_not_red(capsys) -> None:
    """A known-failing test that starts passing is good news, not a build break."""
    output = _run_output([_NODE_A], passed=42)
    assert evaluate(output, {_NODE_A, _NODE_B}) == 0
    out = capsys.readouterr().out
    assert "now passing" in out and _NODE_B in out


def test_an_all_skip_run_cannot_pass(capsys) -> None:
    """The vacuity guard: no failures but nothing executed must FAIL, not pass green."""
    output = _run_output([], passed=9, skipped=34)
    assert evaluate(output, {_NODE_A, _NODE_B}) == 1
    assert "executed" in capsys.readouterr().out


def test_a_count_only_ratchet_would_have_missed_this() -> None:
    """One fixed and one broken in the same run: equal counts, still a regression.

    This is why the baseline is a node-id set rather than an integer like every other
    ratchet in the repo.
    """
    output = _run_output([_NODE_A, _NODE_NEW], passed=41)
    current = failing_node_ids(output)
    baseline = {_NODE_A, _NODE_B}
    assert len(current) == len(baseline)
    assert evaluate(output, baseline) == 1


def test_executed_count_excludes_skips() -> None:
    """Skipped tests are not evidence of execution."""
    assert executed_count("8 failed, 35 passed in 109.10s") == 43
    assert executed_count("9 passed, 34 skipped in 0.28s") == 9


def test_node_ids_are_normalised_from_windows_separators() -> None:
    """pytest reports backslashes on Windows; the baseline is forward-slash only."""
    raw = "FAILED tests\\integration\\test_x.py::test_y - AssertionError\n1 failed in 1s"
    assert failing_node_ids(raw) == {"tests/integration/test_x.py::test_y"}


def test_errors_count_as_failures() -> None:
    """A collection ERROR is a failure for ratchet purposes, not an absence of one."""
    raw = "ERROR tests/integration/test_x.py::test_y\n1 error in 1s"
    assert failing_node_ids(raw) == {"tests/integration/test_x.py::test_y"}


def test_baseline_roundtrips_and_ignores_comments(tmp_path: Path) -> None:
    """The committed baseline carries a header; loading must skip it."""
    path = tmp_path / "integration_baseline.txt"
    write_baseline({_NODE_A, _NODE_B}, path)
    assert path.read_text(encoding="utf-8").startswith("#")
    assert load_baseline(path) == {_NODE_A, _NODE_B}


def test_a_missing_baseline_is_strictest(tmp_path: Path) -> None:
    """No baseline file means every failure is new, never 'anything goes'."""
    assert load_baseline(tmp_path / "absent.txt") == set()


def test_the_committed_baseline_matches_the_measured_failures() -> None:
    """The shipped allowlist holds the 3 remaining after R3 close-out (was 8; ISSUE-233).

    R3 fixed four of the eight: both faction remove-path contracts (a bare count()
    aggregate made their raise guards unreachable) and both scheme tick tests. R3's
    close-out fixed a fifth, the reputation label boundary, once DEC-252 settled that
    standing 50 is `allied` (ISSUE-261). _NODE_A and _NODE_B are both among the fixed and
    are asserted ABSENT; they survive above only as synthetic ids for the parsing tests.
    The three that remain are ISSUE-259 (a test targeting a removed API) and ISSUE-260
    (faction gossip pair truncation, two tests) -- explained, not unexplained, which is
    DEC-250's exit condition.
    """
    baseline = load_baseline()
    assert len(baseline) == 3
    assert _NODE_A not in baseline
    assert _NODE_B not in baseline
    assert all(node.startswith("tests/integration/") for node in baseline)


def test_the_executed_floor_is_below_the_real_run_and_above_an_all_skip() -> None:
    """34 sits between the 9 that run without Neo4j and the 43 that run with it."""
    assert 9 < MIN_EXECUTED_TESTS <= 43
