"""
Module: mutation_probe
Layer: scripts
Purpose: Applies named code mutations one at a time, runs the eval unit test suite,
         and fails (exit 1) if any mutation survives undetected. Proves that
         EVAL-P15.1–P15.5 produced tests that catch the exact structural failures
         the phase was built to detect.
Dependencies: ast, dataclasses, pathlib, subprocess, sys, typing
Used by: make check-mutations, tests/unit/scripts/test_mutation_probe.py
"""
from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]

# Run unit tests only — fast, no real artifacts needed.
SUITE_CMD: tuple[str, ...] = (
    sys.executable, "-m", "pytest",
    "tests/unit/evals/", "tests/unit/scripts/",
    "-q", "--tb=no", "--no-header",
)

Runner = Callable[[Sequence[str], Path], int]


@dataclass(frozen=True)
class Mutation:
    """Named mutation: replace a function's body with a single return statement."""

    name: str
    file: str
    function: str
    replacement_body: str


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        name="matchers.evaluate → return (True, '')",
        file="evals/matchers.py",
        function="evaluate",
        replacement_body="return (True, '')",
    ),
    Mutation(
        name="judge_runner._apply_polarity → return score is True",
        file="evals/judge_runner.py",
        function="_apply_polarity",
        replacement_body="return score is True",
    ),
    Mutation(
        name="case_stats.classify_battery → return 'guard'",
        file="evals/case_stats.py",
        function="classify_battery",
        replacement_body="return 'guard'",
    ),
    Mutation(
        name="calibration._kappa_from_matrix → return 1.0",
        file="evals/calibration.py",
        function="_kappa_from_matrix",
        replacement_body="return 1.0",
    ),
    Mutation(
        name="rate_stats.wilson_interval → return (0.0, 1.0)",
        file="evals/rate_stats.py",
        function="wilson_interval",
        replacement_body="return (0.0, 1.0)",
    ),
)


def _find_function_span(source: str, func_name: str) -> tuple[int, int]:
    """Return (body_start_line, end_line) 1-indexed for the named top-level function.

    Args:
        source: Python source code to search.
        func_name: Name of the top-level function to locate.
    Returns:
        (body_start_line, end_line) both 1-indexed, inclusive.
    Raises:
        ValueError: If func_name is not found as a top-level function.
    """
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != func_name:
            continue
        body_start = node.body[0].lineno
        end = node.end_lineno
        if end is None:
            raise ValueError(f"Function {func_name!r} has no end_lineno (malformed AST)")
        return body_start, end
    raise ValueError(f"Function {func_name!r} not found in source")


def apply_mutation(source: str, func_name: str, replacement_body: str) -> str:
    """Return source with the named function's body replaced by replacement_body.

    The replacement becomes the function's sole body statement, preserving the
    original indentation level of the first body line.

    Args:
        source: Original Python source string.
        func_name: Top-level function to mutate.
        replacement_body: Single Python statement used as the entire new body.
    Returns:
        Mutated source string. The original string is never modified.
    Raises:
        ValueError: If func_name is not found.
    """
    body_start, body_end = _find_function_span(source, func_name)
    lines = source.splitlines(keepends=True)
    first_body_line = lines[body_start - 1]
    indent = " " * (len(first_body_line) - len(first_body_line.lstrip()))
    replacement_line = f"{indent}{replacement_body}\n"
    return "".join(lines[: body_start - 1] + [replacement_line] + lines[body_end:])


def _subprocess_runner(cmd: Sequence[str], cwd: Path) -> int:
    """Run cmd in cwd and return its exit code."""
    result = subprocess.run(list(cmd), cwd=cwd, capture_output=True)
    return result.returncode


def _probe_one(mutation: Mutation, cwd: Path, runner: Runner) -> bool:
    """Apply one mutation, run the suite, restore the file. Returns True if survived.

    The original file is always restored in the finally block, even if the runner
    raises or the mutation causes an import error in the test suite.

    Args:
        mutation: The mutation to apply.
        cwd: Project root directory.
        runner: Callable(cmd, cwd) → exit_code.
    Returns:
        True when the test suite still passes with the mutation applied (survived).
    """
    path = cwd / mutation.file
    original = path.read_text(encoding="utf-8")
    mutated = apply_mutation(original, mutation.function, mutation.replacement_body)
    try:
        path.write_text(mutated, encoding="utf-8")
        return runner(SUITE_CMD, cwd) == 0
    finally:
        path.write_text(original, encoding="utf-8")


def run_probe(
    mutations: Sequence[Mutation] = MUTATIONS,
    *,
    cwd: Path | None = None,
    runner: Runner = _subprocess_runner,
) -> list[str]:
    """Run all mutations and return names of those that survived.

    Args:
        mutations: Sequence of Mutation descriptors to probe (defaults to MUTATIONS).
        cwd: Project root directory (defaults to ROOT inferred from this file's path).
        runner: Callable(cmd, cwd) → exit_code. Inject a mock for testing.
    Returns:
        List of mutation names that survived (test suite passed with mutation applied).
        An empty list means every mutation was killed — the tests are effective.
    """
    effective_cwd = cwd if cwd is not None else ROOT
    survivors: list[str] = []
    for mutation in mutations:
        survived = _probe_one(mutation, effective_cwd, runner)
        status = "SURVIVED" if survived else "killed"
        print(f"  [{status}] {mutation.name}", flush=True)
        if survived:
            survivors.append(mutation.name)
    return survivors


def _force_utf8_streams() -> None:
    """Reconfigure stdout/stderr to UTF-8 so a report glyph cannot crash the probe.

    Mutation names carry →. On a Windows console defaulting to cp1252 that raises
    UnicodeEncodeError, which would turn a passing probe into a crash for a reason
    that has nothing to do with mutation survival. Mirrors `check_human_gates.py`.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass  # Non-reconfigurable stream (pipe/pytest capture) — leave as-is.


def main() -> int:
    """CLI entry point: run seed mutations, exit 1 if any survived."""
    _force_utf8_streams()
    print("mutation_probe: running seed mutations against tests/unit/evals/ ...", flush=True)
    survivors = run_probe()
    if survivors:
        print(f"\nFAIL: {len(survivors)} mutation(s) survived the test suite:", flush=True)
        for name in survivors:
            print(f"  - {name}", flush=True)
        return 1
    print("\nOK: all mutations killed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
