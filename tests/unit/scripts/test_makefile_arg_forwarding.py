"""
Module: tests.unit.scripts.test_makefile_arg_forwarding
Layer: tests
Purpose: Pin that every Makefile target advertising ARGS= actually forwards it.
         `make VAR=value` always succeeds whether or not the recipe expands $(VAR),
         so a target that silently drops ARGS fails in the quietest possible way:
         the caller's flag simply never reaches the program, and every log line
         still claims it did.
Dependencies: shutil, subprocess, pytest
Used by: make test (pytest discovery)

WHY THIS FILE EXISTS
scripts/Run-EvalHarness.ps1 step 3 calls `make eval-judge ... ARGS=--panel`, its
.SYNOPSIS says "Panel judge (mixtral:8x7b + qwen2.5:14b + llama3.1:8b)", and its log
line says "Panel judging...". The eval-judge recipe never expanded $(ARGS), so every
harness run since it shipped judged with a SINGLE judge. Downstream: run_status.json
carries no roster, fleiss_kappa is null, and the instrument-degraded verdict (exit 3,
DEC-196) can never fire from a harness run. Found 2026-08-25; family of ISSUE-127
(nothing catches a Makefile target that rots).

`make -n` is the check because it prints the recipe without running it — the assertion
is about the command that WOULD run, so it costs nothing and cannot touch the engine.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not on PATH")

# (target, extra make variables, the ARGS value that must survive into the recipe).
# Every target here documents ARGS= in its own Makefile comment block.
_ARGS_FORWARDING_TARGETS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("eval-judge", ("TRANSCRIPT=evals/generations/x/outputs.jsonl", "GEN_ID=x"), "--panel"),
    ("eval-generate", (), "--k 3 --gen-id x"),
)


def _dry_run(target: str, variables: tuple[str, ...], args: str) -> str:
    """Return the recipe `make` would execute, without executing it."""
    result = subprocess.run(
        ["make", "-n", target, *variables, f"ARGS={args}"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout


@pytest.mark.parametrize("target,variables,args", _ARGS_FORWARDING_TARGETS)
def test_a_target_that_advertises_args_actually_forwards_them(
    target: str, variables: tuple[str, ...], args: str
) -> None:
    """RED anchor: `make -n eval-judge ARGS=--panel` printed a recipe with no --panel,
    so the harness's panel judging was a no-op that nothing reported."""
    recipe = _dry_run(target, variables, args)
    assert recipe.strip(), f"make -n {target} printed no recipe"
    for token in args.split():
        assert token in recipe, (
            f"'{token}' from ARGS did not reach the {target} recipe — the target accepts "
            f"the variable and silently ignores it:\n{recipe}"
        )


def test_the_judge_target_can_still_run_without_args() -> None:
    """Forwarding must not make ARGS mandatory: every existing caller omits it."""
    result = subprocess.run(
        ["make", "-n", "eval-judge", "TRANSCRIPT=evals/generations/x/outputs.jsonl"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0
    assert "evals judge" in result.stdout


# ---------------------------------------------------------------------------
# eval-retrieval: the target that made mean_precision_at_k permanently null
# ---------------------------------------------------------------------------


def _dry_run_vars(target: str, variables: tuple[str, ...]) -> str:
    """Return the recipe `make` would execute for a target driven by variables, not ARGS."""
    result = subprocess.run(
        ["make", "-n", target, *variables],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout


def test_eval_retrieval_forwards_gen_id_as_a_container_path() -> None:
    """RED anchor: the recipe ran `python -m evals retrieval` with NO arguments, so
    retrieval_metrics.json was never written and every trend row carried
    mean_precision_at_k=null -- retrieval quality was the one contract metric that could
    not be trended, compared or gated.

    The path must be the CONTAINER path: the target runs inside the app container because
    neo4j publishes no host port (ISSUE-131), so a host path would not resolve there.
    """
    recipe = _dry_run_vars("eval-retrieval", ("GEN_ID=x", "RETRIEVAL_PROFILE=aggressive"))
    assert "--gen-dir /work/evals/generations/x" in recipe, recipe
    assert "--retrieval-profile aggressive" in recipe, recipe


def test_eval_retrieval_stays_print_only_when_given_no_variables() -> None:
    """Both variables are optional: `make eval-retrieval` alone must keep its original
    print-the-numbers-and-persist-nothing behaviour, which several callers still rely on."""
    recipe = _dry_run_vars("eval-retrieval", ())
    assert "evals retrieval" in recipe
    assert "--gen-dir" not in recipe
    assert "--retrieval-profile" not in recipe
