"""
Module: test_ci_runs_the_full_gate
Layer: test (unit)
Purpose: Pin CI to the canonical gate — every prerequisite of the Makefile `check`
         target must be reachable from `.github/workflows/ci.yml`, so the two cannot
         drift apart again.
Dependencies: pathlib, re; tests.unit.evals.test_gate_scope (Makefile parser)
Used by: pytest (make test / make check)

Why this exists: CI ran 6 of `check`'s 17 targets while every one of the other 11 passed
locally, so eleven gates were enforced on no push for months. The count had already rotted
in the written plan too — FIX_PLANS said "the 8 currently-skipped gates" because it was 8
when that line was written, before R1.8 added 3 and R2.3 added 2 (DEC-238).

That rot is the reason this test **derives** the expected set from the Makefile instead of
listing target names. A hardcoded list is the same failure mode one level up: it would go
stale the next time a gate is added, and pass while doing so.

Reachability, deliberately, is satisfied either by CI running the aggregate `make check`
or by CI naming the individual target. DEC-238 chose the aggregate; this test does not
mandate that choice, it only forbids a prerequisite that no CI job runs at all.

Static parse only — reads the Makefile and the workflow YAML, runs no subprocess.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "tests" / "unit" / "evals"))

from test_gate_scope import prerequisites, read_makefile  # noqa: E402

_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_CHECK_TARGET = "check"
_AGGREGATE_TARGET = "check"

# `make <target>` as it appears in a workflow `run:` line. Tolerates flags and trailing
# arguments (`make check ARGS=...`) but requires the target to be a whole word.
_MAKE_INVOCATION = re.compile(r"\bmake\s+(?:-\S+\s+)*([A-Za-z0-9_.-]+)")


def read_workflow() -> str:
    """Return the CI workflow source text."""
    return _WORKFLOW.read_text(encoding="utf-8")


def make_targets_invoked(workflow: str) -> set[str]:
    """Return every make target named by a `run:` line in the workflow.

    Matrix expansions (`make ${{ matrix.target }}`) cannot be resolved statically, so the
    literal matrix entries are collected separately by `matrix_targets`.
    """
    return {match.group(1) for match in _MAKE_INVOCATION.finditer(workflow)}


def matrix_targets(workflow: str) -> set[str]:
    """Return target names listed under a `strategy.matrix.target:` block.

    The block is a YAML list of bare scalars; parsing stops at the first line that is not
    a `- item` entry, which is how the surrounding job keys terminate it.
    """
    targets: set[str] = set()
    lines = workflow.splitlines()
    for index, line in enumerate(lines):
        if not re.match(r"^\s*target:\s*$", line):
            continue
        for candidate in lines[index + 1 :]:
            item = re.match(r"^\s*-\s+([A-Za-z0-9_.-]+)\s*$", candidate)
            if item is None:
                break
            targets.add(item.group(1))
    return targets


def unreachable_prerequisites() -> list[str]:
    """Return `check` prerequisites that no CI job runs, directly or via the aggregate."""
    workflow = read_workflow()
    invoked = make_targets_invoked(workflow) | matrix_targets(workflow)
    if _AGGREGATE_TARGET in invoked:
        return []
    required = prerequisites(read_makefile(), _CHECK_TARGET)
    return [target for target in required if target not in invoked]


def test_every_check_prerequisite_is_reachable_from_ci() -> None:
    """No gate may sit in `make check` while no CI job ever runs it."""
    missing = unreachable_prerequisites()
    assert not missing, (
        f"{len(missing)} `make check` prerequisite(s) never run in CI: "
        f"{', '.join(missing)}. Either CI runs `make check` (DEC-238) or it names the "
        f"target explicitly. Do not fix this by removing the target from `check`."
    )


def test_check_still_has_prerequisites_to_guard() -> None:
    """Guard the guard: a `check` target parsed as empty would pass vacuously."""
    assert len(prerequisites(read_makefile(), _CHECK_TARGET)) >= 15


def test_the_two_coverage_gates_are_inside_check() -> None:
    """`test-cov-v13` and `test-cov-full-report` belong to `check`, not only to CI.

    DEC-238: they were `verify-v13` prerequisites that CI ran directly, so collapsing the
    coverage job without folding them in would have silently deleted two gates.
    """
    required = prerequisites(read_makefile(), _CHECK_TARGET)
    for target in ("test-cov-v13", "test-cov-full-report"):
        assert target in required, f"{target} must be a `check` prerequisite (DEC-238)"


def test_matrix_targets_are_counted_as_reachable() -> None:
    """A target run only through a `matrix.target` list still counts as reachable."""
    workflow = "\n".join(
        [
            "jobs:",
            "  m:",
            "    strategy:",
            "      matrix:",
            "        target:",
            "          - test-v13-contracts",
            "          - test-v13-retrieval",
            "    steps:",
            "      - run: make ${{ matrix.target }}",
        ]
    )
    assert matrix_targets(workflow) == {"test-v13-contracts", "test-v13-retrieval"}


def test_make_invocation_parser_finds_plain_targets() -> None:
    """The `run:` scanner picks up ordinary `make <target>` steps."""
    assert make_targets_invoked("      - run: make check-rules\n") == {"check-rules"}
    assert "check" in make_targets_invoked("        run: make check\n")
