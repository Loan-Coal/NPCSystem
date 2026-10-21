"""
Module: test_expand_loop_night_guard
Layer: test (unit)
Purpose: Pin the three between-nights guards added by T21.3:
    1. Preflight helper (check_unverified_ticks) blocks when a task line carries an
       UNVERIFIED tick marker; passes when the marker appears only in prose.
    2. Baseline-drift helper (check_gate_baseline_drift) returns 2 when
       gate_baseline.json changes during a task session.
    3. write_night_tag writes a loop-night-<date> git tag at run end.
Does NOT: launch claude, touch the live roadmap, or run the full loop.
Dependencies: scripts/expand_loop.sh (sourced, main guarded by BASH_SOURCE), Git Bash.
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GIT_BASH = Path("C:/Program Files/Git/bin/bash.exe")

pytestmark = pytest.mark.skipif(
    not _GIT_BASH.exists(), reason="Git Bash required to source the loop script"
)

# Markers used by _roadmap_cursor_core.py:47
_UNVERIFIED_MARKER = "AUTO ⚠️ UNVERIFIED"

_ROADMAP_TICK_LINE = (
    "- [x] **T1.1** some task ✅ " + _UNVERIFIED_MARKER + " (T1.1, regression, 2026-10-21)\n"
)
_ROADMAP_PROSE_LINE = (
    "The " + _UNVERIFIED_MARKER + " marker means a task needs human review.\n"
)


def _run_bash(
    harness: str,
    *,
    extra_env: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run a bash harness string in Git Bash from _REPO_ROOT and return the result."""
    env = {**os.environ, **(extra_env or {})}
    return subprocess.run(
        [str(_GIT_BASH), "-c", harness],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


# ---------------------------------------------------------------------------
# 1. UNVERIFIED tick refusal
# ---------------------------------------------------------------------------

_HARNESS_UNVERIFIED = """\
source scripts/expand_loop.sh
ROADMAP_FILE="$FIXTURE_FILE"
check_unverified_ticks
echo "rc=$?"
"""


def _run_unverified_check(fixture_path: Path) -> int:
    """Return the exit code of check_unverified_ticks on *fixture_path*."""
    result = _run_bash(
        _HARNESS_UNVERIFIED,
        extra_env={"FIXTURE_FILE": fixture_path.as_posix()},
    )
    for line in result.stdout.splitlines():
        if line.startswith("rc="):
            return int(line[3:])
    pytest.fail(
        f"harness did not print rc=: stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_unverified_tick_on_task_line_blocks(tmp_path: Path) -> None:
    """check_unverified_ticks returns 0 (found) when a task line has the UNVERIFIED marker."""
    fixture = tmp_path / "roadmap.md"
    fixture.write_text(_ROADMAP_TICK_LINE, encoding="utf-8")

    rc = _run_unverified_check(fixture)

    assert rc == 0, (
        f"expected 0 (UNVERIFIED tick found on task line), got {rc}"
    )


def test_unverified_in_prose_does_not_block(tmp_path: Path) -> None:
    """check_unverified_ticks returns non-0 (not found) when marker appears only in prose."""
    fixture = tmp_path / "roadmap.md"
    fixture.write_text(_ROADMAP_PROSE_LINE, encoding="utf-8")

    rc = _run_unverified_check(fixture)

    assert rc != 0, (
        f"expected non-0 (UNVERIFIED not on a task line), got {rc}"
    )


# ---------------------------------------------------------------------------
# 2. Gate-baseline drift detection
# ---------------------------------------------------------------------------

_HARNESS_BASELINE_DRIFT = """\
source scripts/expand_loop.sh
LOOP_STATE_DIR="$TEST_STATE_DIR"
flag_for_human() { echo "FLAG: $1"; }
log() { :; }
check_gate_baseline_drift PHASE TASK "$HASH_BEFORE"
echo "rc=$?"
"""


def _run_baseline_check(state_dir: Path, hash_before: str) -> tuple[int, str]:
    """Run check_gate_baseline_drift and return (rc, stdout)."""
    result = _run_bash(
        _HARNESS_BASELINE_DRIFT,
        extra_env={
            "TEST_STATE_DIR": state_dir.as_posix(),
            "HASH_BEFORE": hash_before,
        },
    )
    for line in result.stdout.splitlines():
        if line.startswith("rc="):
            return int(line[3:]), result.stdout
    pytest.fail(
        f"harness did not print rc=: stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_gate_baseline_drift_halts(tmp_path: Path) -> None:
    """check_gate_baseline_drift returns 2 and calls flag_for_human when the file changes."""
    bfile = tmp_path / "gate_baseline.json"
    bfile.write_text('{"tests": ["old::test"]}', encoding="utf-8")

    hash_before = (
        subprocess.check_output(
            [str(_GIT_BASH), "-c", f'sha256sum "{bfile.as_posix()}" | awk \'{{print $1}}\''],
            cwd=_REPO_ROOT,
            text=True,
        ).strip()
    )

    # Simulate the session modifying the baseline.
    bfile.write_text('{"tests": ["old::test", "new::test"]}', encoding="utf-8")

    rc, stdout = _run_baseline_check(tmp_path, hash_before)

    assert rc == 2, f"expected return 2 (drift detected), got {rc}"
    assert "FLAG" in stdout, f"expected flag_for_human call, got: {stdout!r}"


def test_gate_baseline_no_change_passes(tmp_path: Path) -> None:
    """check_gate_baseline_drift returns 0 when the baseline file is unchanged."""
    bfile = tmp_path / "gate_baseline.json"
    bfile.write_text('{"tests": ["old::test"]}', encoding="utf-8")

    hash_before = (
        subprocess.check_output(
            [str(_GIT_BASH), "-c", f'sha256sum "{bfile.as_posix()}" | awk \'{{print $1}}\''],
            cwd=_REPO_ROOT,
            text=True,
        ).strip()
    )

    rc, stdout = _run_baseline_check(tmp_path, hash_before)

    assert rc == 0, f"expected return 0 (no drift), got {rc}"
    assert "FLAG" not in stdout, f"expected no flag_for_human call, got: {stdout!r}"


# ---------------------------------------------------------------------------
# 3. Night tag
# ---------------------------------------------------------------------------

_HARNESS_NIGHT_TAG = """\
source scripts/expand_loop.sh
log() { :; }
write_night_tag
echo "rc=$?"
"""


def test_night_tag_written() -> None:
    """write_night_tag creates a loop-night-<date> tag in the current repo."""
    result = _run_bash(_HARNESS_NIGHT_TAG)

    for line in result.stdout.splitlines():
        if line.startswith("rc="):
            rc = int(line[3:])
            break
    else:
        pytest.fail(
            f"harness did not print rc=: stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    assert rc == 0, f"write_night_tag returned {rc}: stderr={result.stderr!r}"

    tags_out = subprocess.check_output(
        ["git", "tag", "--list", "loop-night-*"],
        cwd=_REPO_ROOT,
        text=True,
    ).strip()
    assert tags_out, f"no loop-night-* tag found after write_night_tag ran"
