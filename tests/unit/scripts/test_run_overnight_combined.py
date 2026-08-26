"""
Module: tests.unit.scripts.test_run_overnight_combined
Layer: tests
Purpose: Pin the preconditions and wiring of project-harness/Run-OvernightCombined.ps1 by
         asserting on its source text. The script is a ~10-hour unattended ops run, so its
         defects are only ever discovered the morning after; a static assertion is the only
         check that costs nothing and still fires.
Dependencies: pathlib, pytest
Used by: make test (pytest discovery)

WHY THIS FILE EXISTS
The 2026-08-25 run spent 5h37m and produced an arm whose provenance is false: step 3 ran
`docker-compose up -d`, which reused an image built 2026-08-18, so the engine under test was
missing the three commits that ARE the A/B feature set. DialogueRequest is frozen but not
extra='forbid', so the stale engine silently DROPPED retrieval_profile and the run would have
reported two identical arms as "retrieval has no effect". Nothing in the pipeline asserted
which build was answering.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "project-harness" / "Run-OvernightCombined.ps1"


def _source() -> str:
    return _SCRIPT.read_text(encoding="utf-8")


def test_script_exists() -> None:
    assert _SCRIPT.exists()


# ---------------------------------------------------------------------------
# Step 3 — the build the run is actually attributed to
# ---------------------------------------------------------------------------


def test_step_three_rebuilds_the_app_image_stamped_with_the_preflight_sha() -> None:
    """RED anchor: `docker-compose up -d` happily serves a stale image. Step 1 captures
    $Sha and the handoff reports it as "commit under test", so step 3 must actually BUILD
    that SHA rather than assume whatever image is lying around is it."""
    source = _source()
    assert "BUILD_SHA" in source, "step 3 must stamp the image with the SHA the run claims"
    assert "up -d --build app" in source, "step 3 must rebuild the app image, not reuse it"


def test_step_three_asserts_the_running_build_before_seeding() -> None:
    """Building is not enough: `up -d` can still serve a cached container. The run must
    assert /health's reported SHA via the existing boot_check.py gate, and must do it
    BEFORE seeding or generating -- an assertion after the spend is a post-mortem."""
    source = _source()
    assert "boot_check.py" in source
    assert "--expect-sha" in source

    boot_at = source.index("boot_check.py")
    seed_at = source.index("$seedTarget")
    assert boot_at < seed_at, "the build assertion must run before the seed loop"


def test_a_stale_build_aborts_the_run_rather_than_warning() -> None:
    """A warning in a 10-hour unattended log is a warning nobody reads. The whole point is
    turning 5h37m of false provenance into a fast abort, so the boot check's exit code must
    be tested and the run stopped."""
    source = _source()
    boot_at = source.index("boot_check.py")
    following = source[boot_at : boot_at + 800]
    assert "LASTEXITCODE" in following, "the boot check's exit code must be inspected"
    assert "exit 3" in following, "a stale build must abort step 3, not merely log"


# ---------------------------------------------------------------------------
# Retrieval metrics — the file trend_row_builder reads and nothing ever wrote
# ---------------------------------------------------------------------------


def _retrieval_call_index(source: str) -> int:
    """Index of the pipeline's retrieval-measurement invocation, or -1 when absent."""
    return source.find("evals retrieval")


def test_the_pipeline_measures_retrieval_between_generation_and_the_trend_row() -> None:
    """RED anchor: trend_row_builder reads mean_precision_at_k from the gen dir's
    retrieval_metrics.json, and NOTHING in any pipeline ever created that file -- so every
    recorded row carried mean_precision_at_k=null. The measurement must happen after the
    arm exists (step 4) and before the row is recorded (step 9), or it records nothing."""
    source = _source()
    call_at = _retrieval_call_index(source)
    assert call_at != -1, "the pipeline never measures retrieval, so the trend row cannot carry it"
    assert "--gen-dir" in source[call_at : call_at + 600], "the measurement must be persisted to the arm"

    generate_at = source.index("STEP 4/10")
    trend_at = source.index("Steps 9-10: EVAL-P22B")
    assert generate_at < call_at < trend_at


def test_a_retrieval_failure_is_reported_but_does_not_kill_the_run() -> None:
    """By this point the run has already spent ~85 minutes generating. A missing precision
    number is a finding to read in the morning, not a reason to discard the arm -- so the
    exit code is logged like every sibling step and never acted on."""
    source = _source()
    call_at = _retrieval_call_index(source)
    following = source[call_at : call_at + 600]
    assert "LASTEXITCODE" in following, "the exit code must be logged, not swallowed"
    assert re.search(r"(?m)^\s*exit\s+\d", following) is None, (
        "a retrieval failure must not abort the run"
    )


# ---------------------------------------------------------------------------
# The API key the child powershell.exe inherits
# ---------------------------------------------------------------------------


def test_the_api_key_is_exported_before_the_resume_branch() -> None:
    """RED anchor: the key was read from .env INSIDE steps 1-8 and kept in a local $ApiKey,
    so Run-EvalHarness.ps1's preflight (which reads $env:API_KEY_SECRET) saw nothing -- and
    -ResumeGenId, which runs step 10 directly, never reached the read at all.

    The export must happen above the resume branch, or the resumed path still hands the child
    an empty environment."""
    source = _source()
    assert "$env:API_KEY_SECRET" in source, "the key must reach the child process's environment"

    export_at = source.index("$env:API_KEY_SECRET")
    resume_at = source.index("if ($ResumeGenId) {")
    assert export_at < resume_at, "the resume path must export the key too"
