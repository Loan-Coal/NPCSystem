"""
Module: tests.unit.scripts.test_mutation_probe
Layer: tests
Purpose: Unit tests for scripts/mutation_probe.py — verifies that surviving mutations
         are reported (gate returns non-empty list), killed mutations are not, files are
         restored after probing, apply_mutation produces valid Python, and all 5 seed
         mutations from the EVAL-P15.6 spec are present in MUTATIONS.
Dependencies: ast, pathlib, sys, pytest, mutation_probe
Used by: make test (pytest discovery)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from mutation_probe import (  # noqa: E402
    MUTATIONS,
    Mutation,
    apply_mutation,
    run_probe,
)

_SAMPLE_SOURCE = '''\
def greet(name: str) -> str:
    """Greet by name."""
    prefix = "Hello"
    return f"{prefix}, {name}!"
'''


# ---------------------------------------------------------------------------
# RED anchor — must fail before mutation_probe.py exists (ImportError)
# ---------------------------------------------------------------------------


def test_surviving_mutation_fails_the_gate(tmp_path: Path) -> None:
    """run_probe returns the mutation name when the suite passes with mutation applied.

    A runner returning 0 means tests still pass → the mutation survived → the gate
    must report it.  The gate fails (non-empty survivor list) so the caller exits 1.
    """
    target = tmp_path / "sample.py"
    target.write_text(_SAMPLE_SOURCE, encoding="utf-8")
    mutation = Mutation(
        name="test.greet → return ''",
        file="sample.py",
        function="greet",
        replacement_body="return ''",
    )
    # Runner returns 0: tests still pass → mutation survived
    survivors = run_probe([mutation], cwd=tmp_path, runner=lambda cmd, cwd: 0)
    assert len(survivors) == 1
    assert survivors[0] == mutation.name


# ---------------------------------------------------------------------------
# Killed mutation — suite returns non-zero → not in survivors
# ---------------------------------------------------------------------------


def test_killed_mutation_is_not_reported(tmp_path: Path) -> None:
    """run_probe returns empty list when the suite fails with mutation applied."""
    target = tmp_path / "sample.py"
    target.write_text(_SAMPLE_SOURCE, encoding="utf-8")
    mutation = Mutation(
        name="test.greet → return ''",
        file="sample.py",
        function="greet",
        replacement_body="return ''",
    )
    # Runner returns 1: tests fail → mutation was killed
    survivors = run_probe([mutation], cwd=tmp_path, runner=lambda cmd, cwd: 1)
    assert survivors == []


# ---------------------------------------------------------------------------
# File restoration — always, even when mutation survives
# ---------------------------------------------------------------------------


def test_file_is_restored_after_probe(tmp_path: Path) -> None:
    """Source file is restored to original content after probing regardless of outcome."""
    target = tmp_path / "sample.py"
    target.write_text(_SAMPLE_SOURCE, encoding="utf-8")
    mutation = Mutation(
        name="test.greet → return ''",
        file="sample.py",
        function="greet",
        replacement_body="return ''",
    )
    run_probe([mutation], cwd=tmp_path, runner=lambda cmd, cwd: 0)
    assert target.read_text(encoding="utf-8") == _SAMPLE_SOURCE


# ---------------------------------------------------------------------------
# apply_mutation correctness
# ---------------------------------------------------------------------------


def test_apply_mutation_replaces_function_body() -> None:
    """apply_mutation replaces the function body with a single return statement."""
    mutated = apply_mutation(_SAMPLE_SOURCE, "greet", "return ''")
    tree = ast.parse(mutated)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "greet":
            assert len(node.body) == 1
            assert isinstance(node.body[0], ast.Return)
            return
    pytest.fail("greet function not found in mutated source")


def test_apply_mutation_produces_valid_python() -> None:
    """The mutated source can be parsed by ast.parse (no SyntaxError)."""
    mutated = apply_mutation(_SAMPLE_SOURCE, "greet", "return ''")
    ast.parse(mutated)  # raises SyntaxError if invalid


def test_apply_mutation_raises_on_missing_function() -> None:
    """apply_mutation raises ValueError when the function name is not found."""
    with pytest.raises(ValueError, match="not found"):
        apply_mutation(_SAMPLE_SOURCE, "nonexistent_func", "return 0")


# ---------------------------------------------------------------------------
# Seed mutations completeness
# ---------------------------------------------------------------------------


def test_all_seed_mutations_are_present() -> None:
    """MUTATIONS contains all 5 named seed mutations from the EVAL-P15.6 spec."""
    expected = {
        "matchers.evaluate → return (True, '')",
        "judge_runner._apply_polarity → return score is True",
        "case_stats.classify_battery → return 'guard'",
        "calibration._kappa_from_matrix → return 1.0",
        "rate_stats.wilson_interval → return (0.0, 1.0)",
    }
    assert {m.name for m in MUTATIONS} == expected
