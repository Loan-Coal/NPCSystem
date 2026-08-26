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
