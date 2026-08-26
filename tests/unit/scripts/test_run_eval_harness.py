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

import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "Run-EvalHarness.ps1"

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="PowerShell script, Windows-only")

def _artifact_path_prefixes() -> list[str]:
    """Parse $ArtifactPathPrefixes out of the real script.

    Read from the script rather than duplicated here: a list that drifts from the one
    the precondition actually applies would assert nothing.
    """
    source = _SCRIPT.read_text(encoding="utf-8")
    block = re.search(r"\$ArtifactPathPrefixes\s*=\s*@\((.*?)\)", source, re.DOTALL)
    assert block, "$ArtifactPathPrefixes not found in the script"
    return re.findall(r'"([^"]+)"', block.group(1))



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
# The resolved repo root — the defect that made this script unrunnable
# ---------------------------------------------------------------------------


def _reported_repo_root(stdout: str) -> Path:
    """Extract the root the script says it resolved, from its own output."""
    for line in stdout.splitlines():
        if line.startswith(_ROOT_PREFIX):
            return Path(line[len(_ROOT_PREFIX) :].strip())
    raise AssertionError(f"script never reported its repo root (prefix {_ROOT_PREFIX!r})")


_ROOT_PREFIX = "Repo root: "


def test_dry_run_reports_a_repo_root_that_holds_the_makefile() -> None:
    """RED anchor: the script lived in scripts/ but resolved its root with TWO
    `Split-Path -Parent` calls, landing on the PARENT of the repo. Every `make`
    invocation then ran where there is no Makefile, so the run died at step 2 --
    and no test caught it, because --DryRun exits before the make calls and the
    precondition tests all fail at check 1. The resolved root must contain the
    Makefile the script shells out to."""
    result = _run("-DryRun", timeout=15)
    assert result.returncode == 0
    root = _reported_repo_root(result.stdout)
    assert (root / "Makefile").is_file(), f"resolved root {root} holds no Makefile"


def test_dry_run_reports_a_repo_root_that_is_a_git_repository() -> None:
    """The same defect made the clean-tree precondition VACUOUS: `git status
    --porcelain` outside a work tree writes to stderr and returns nothing on
    stdout, so IsNullOrWhiteSpace($status) read True and 'working tree clean'
    passed against a dirty tree. The root must be a real work tree."""
    result = _run("-DryRun", timeout=15)
    assert result.returncode == 0
    root = _reported_repo_root(result.stdout)
    assert (root / ".git").exists(), f"resolved root {root} is not a git repository"


def test_repo_root_resolution_fails_loudly_when_it_finds_no_repo() -> None:
    """A silently-wrong root is what caused this defect, so the resolution must
    assert its result rather than trust the arithmetic."""
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "Makefile" in source, "root resolution must verify it found the repo"


def test_preflight_asserts_the_running_build_is_not_a_stale_image() -> None:
    """RED anchor for the 2026-08-25 false-provenance run: `docker-compose up -d` served an
    image built a week earlier, so the engine under test was missing the very commits the
    A/B was measuring -- and DialogueRequest, frozen but not extra='forbid', silently
    dropped retrieval_profile. Preflight must assert the running build's SHA against the
    source SHA using the existing e2e/scripts/boot_check.py gate, which already implements
    exactly this check and was in no pipeline."""
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "boot_check.py" in source
    assert "--expect-sha" in source


def test_clean_tree_precondition_asserts_it_is_inside_a_work_tree() -> None:
    """Empty `git status` output is ambiguous -- it means both 'clean' and 'not
    a repository'. The precondition must disambiguate, so it can never again
    report OK from outside a work tree."""
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "--is-inside-work-tree" in source


def test_clean_tree_precondition_ignores_harness_written_artifact_paths() -> None:
    """The precondition exists to attribute a run to a known engine SHA, so it
    must refuse a dirty SOURCE tree -- but the pipeline's own outputs do not
    change the engine. Without this exclusion, step 10 of Run-OvernightCombined
    (EVAL-P22B.2) can never run: by then step 7 has written the tracked
    judged.jsonl, which that script documents as dirty-by-design."""
    source = _SCRIPT.read_text(encoding="utf-8")
    for artifact_dir in ("evals/generations/", "evals/reports/", "project-harness/overnight_logs/"):
        assert artifact_dir in source, f"{artifact_dir} must be excluded from the clean-tree check"


# ---------------------------------------------------------------------------
# The world-seeded preflight — two independent bugs, both fatal
# ---------------------------------------------------------------------------


def _world_seeded_precondition() -> str:
    """The eval-worlds-seeded precondition's CODE, comments stripped.

    Comments are dropped because the block explains the header bug in prose; asserting over
    the raw text would let a comment satisfy — or violate — a claim about what is sent.
    """
    raw = _SCRIPT.read_text(encoding="utf-8").splitlines()
    source = "\n".join(ln for ln in raw if not ln.strip().startswith("#"))
    start = source.index('Test-EnginePrecondition "eval worlds seeded')
    end = source.find("Test-EnginePrecondition", start + 1)
    return source[start:] if end == -1 else source[start:end]


def test_the_world_seeded_preflight_authenticates_with_a_bearer_token() -> None:
    """RED anchor: it sent the header 'X-API-Key'. The engine requires
    'Authorization: Bearer' (src/npc_engine/auth/api_key.py:20), so every request 401'd,
    Invoke-WebRequest threw, Test-EnginePrecondition's catch swallowed it, and the failure
    was reported as "eval worlds seeded" -- a precondition that has never once passed while
    naming the wrong cause. Pinned so an edit back to X-API-Key fails a test."""
    body = _world_seeded_precondition()
    assert "Bearer" in body
    assert "Authorization" in body
    assert "X-API-Key" not in body


def test_the_api_key_is_resolvable_without_an_exported_variable() -> None:
    """The second, independent bug: it read $env:API_KEY_SECRET, which nothing exported --
    Run-OvernightCombined kept the key in a local. Standalone `make eval-harness` exports
    nothing either, so the key must also be resolvable from .env, the same line the Makefile
    reads."""
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "API_KEY_SECRET" in source
    assert ".env" in source


def test_a_missing_api_key_fails_the_precondition_instead_of_sending_no_header() -> None:
    """Sending no header at all turns a configuration mistake into a 401 reported as
    "worlds not seeded". An absent key must fail loudly, naming itself."""
    body = _world_seeded_precondition()
    assert re.search(r"if \(-not \$apiKey\)", body), (
        "the precondition must guard on a missing key rather than sending an empty header"
    )
    assert "return $false" in body


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


def test_pipeline_written_artifacts_are_exempt_from_the_clean_tree_precondition() -> None:
    """RED anchor for the step-10 blocker found 2026-08-25.

    Run-OvernightCombined.ps1 step 8 writes evals/calibration/label_order_<gen>.* and
    step 9 writes evals/trend/trend_v1.jsonl, then step 10 runs THIS script — whose
    clean-tree precondition treats anything outside $ArtifactPathPrefixes as a source
    change. Neither path is gitignored, so step 9 created the file that made step 10
    abort one line later, and EVAL-P22B.2 could never pass.

    These are outputs of the pipeline being run, not engine changes, so exempting them
    does not weaken what the precondition is for (attributing the run to a known SHA).
    evals/calibration/ as a WHOLE stays in scope on purpose: labels_v1.jsonl is a real
    input to calibration, and an uncommitted edit to it must still fail preflight."""
    prefixes = _artifact_path_prefixes()

    exempt = [
        "evals/generations/k3_abc1234_regen1/judged.jsonl",
        "evals/reports/report.md",
        "project-harness/overnight_logs/phase1.log",
        "evals/trend/trend_v1.jsonl",
        "evals/calibration/label_order_k3_abc1234_regen1.order.txt",
        "evals/calibration/label_order_k3_abc1234_regen1.coverage_gaps.txt",
    ]
    for path in exempt:
        assert any(path.startswith(p) for p in prefixes), f"{path} would abort preflight"

    still_in_scope = [
        "src/npc_engine/engines/dialogue/dialogue_handler.py",
        "evals/cases/case_001_grieving_elder.yaml",
        "evals/calibration/labels_v1.jsonl",  # a real calibration input, not an artifact
        "scripts/Run-EvalHarness.ps1",
    ]
    for path in still_in_scope:
        assert not any(path.startswith(p) for p in prefixes), (
            f"{path} must still count as a source change"
        )
