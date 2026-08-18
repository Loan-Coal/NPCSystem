"""
Module: tests.unit.scripts.test_run_eval_harness
Layer: tests
Purpose: Integration-level tests for scripts/Run-EvalHarness.ps1 (EVAL-P23.3) --
         shells out to the real script via powershell.exe. --dry-run must
         terminate immediately (ISSUE-126 is the standing reminder that a
         --dry-run which hangs is worse than none); a real run against a
         down engine must exit non-zero, naming the failed precondition,
         before generating anything.
Dependencies: subprocess, pathlib, pytest, sys
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "Run-EvalHarness.ps1"

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="PowerShell script, Windows-only")


def _run(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(_SCRIPT), *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_script_exists() -> None:
    assert _SCRIPT.exists()


def test_dry_run_terminates_and_prints_the_plan() -> None:
    """ISSUE-126: a --dry-run that hangs or partially executes is worse than
    none. This test's own `timeout=` is the enforcement mechanism -- a hang
    fails the test rather than the suite."""
    result = _run("-DryRun", timeout=15)
    assert result.returncode == 0
    assert "plan" in result.stdout.lower()
    assert "preflight" in result.stdout.lower()  # names the step, doesn't run it
    assert "generate" in result.stdout.lower()


def test_dry_run_does_not_check_any_precondition() -> None:
    """--dry-run must print the plan without touching the engine, ollama, or
    git status -- confirmed by the absence of a real precondition-check
    result line (Test-EnginePrecondition's own "Preflight OK:"/"Preflight
    FAILED:" format; step 1 of the static $Plan array legitimately contains
    the word "Preflight" as a label, so that alone isn't the right check)."""
    result = _run("-DryRun")
    assert "Preflight OK:" not in result.stdout
    assert "Preflight FAILED:" not in result.stdout


def test_harness_exits_nonzero_when_a_precondition_fails() -> None:
    """The RED anchor: with the engine unreachable (the ambient state of this
    checkout during a unit-test run -- no docker-compose stack is up), the
    harness must exit non-zero and name the failed precondition, before
    attempting to generate anything."""
    result = _run(timeout=15)
    assert result.returncode == 2
    combined = result.stdout + result.stderr
    assert "Precondition failed" in combined
    assert "engine reachable" in combined
    # must fail during preflight, never reach the generation step
    assert "[2/8]" not in combined


def test_harness_accepts_a_custom_base_url_and_still_fails_loudly() -> None:
    """A precondition failure against an explicitly-wrong URL must be just as
    loud as the default -- the -BaseUrl parameter is honoured, not ignored."""
    result = _run("-BaseUrl", "http://localhost:1", timeout=15)
    assert result.returncode == 2
    assert "Precondition failed" in (result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# One baseline, used by both steps — EVAL-P23 Defect A
# ---------------------------------------------------------------------------


def test_the_compare_step_does_not_hardcode_a_baseline_gen_id() -> None:
    """RED anchor for Defect A: step 7 hardcoded BEFORE=k3_73e6c36 while step 8
    gated against the trend store, so the per-case delta table and the
    authoritative verdict described DIFFERENT comparisons — and k3_73e6c36 can
    never compare at all (ISSUE-186: harness_version None), which made step 7
    permanently inert. The baseline must be resolved once and passed to both."""
    source = _SCRIPT.read_text(encoding="utf-8")
    compare_lines = [ln for ln in source.splitlines() if "eval-compare" in ln and not ln.strip().startswith("#")]
    assert compare_lines, "step 7 must still call eval-compare"
    for line in compare_lines:
        assert "k3_73e6c36" not in line
        assert "$Baseline" in line  # the resolved baseline, not a literal


def test_dry_run_plan_names_the_baseline_resolution_step() -> None:
    """The plan a human reads before a real run must say that the baseline is
    resolved once and shared, and that step 7 is skipped when there is none."""
    result = _run("-DryRun", timeout=15)
    assert result.returncode == 0
    plan = result.stdout.lower()
    assert "baseline" in plan
    assert "skip" in plan  # the empty-trend-store path is explicit, not silent


def test_dry_run_accepts_an_explicit_baseline_parameter() -> None:
    """-Baseline is a real parameter, not an ignored extra argument: an unknown
    parameter makes PowerShell fail the binding and exit non-zero."""
    result = _run("-DryRun", "-Baseline", "some_prior_gen", timeout=15)
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Four distinct verdicts — EVAL-P23 Defect E
# ---------------------------------------------------------------------------


def test_harness_reports_instrument_degraded_as_its_own_state() -> None:
    """Defect E: exit 3 (judge agreement fell — the rate comparison is not
    trustworthy and the engine is not necessarily at fault) must be reported
    distinctly from exit 1 (engine regression) and exit 2 (setup error).
    Verified statically because reaching exit 3 needs a full live run, which
    this suite must never trigger (the generation paths are frozen)."""
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "$gateExit -eq 3" in source
    assert "INSTRUMENT DEGRADED" in source
    assert "REGRESSION" in source
    assert "SETUP ERROR" in source
    # the exit-code contract in .DESCRIPTION must document the new state too
    assert "3 = " in source
