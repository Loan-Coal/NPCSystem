"""
Module: test_expand_loop_frozen_paths
Layer: test (unit)
Purpose: Pin that check_frozen_paths halts and resets HEAD when a task session commits
    to a frozen path, returns 0 for allowed paths, and detects history rewrites (T21.4, DEC-316).
Does NOT: launch claude, touch the live roadmap, or run the full loop.
Dependencies: scripts/expand_loop.sh (sourced, main guarded by BASH_SOURCE), Git Bash.
Used by: pytest (make test / make check)

Why this exists: DEC-316 requires a narrow, driver-fixed list of paths that no task
session may write to. A hit must end the night and reset HEAD so the tampered commit is
never left in the branch. This test pins all three required behaviours.
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

# Base harness used by calibration and tests-only cases.
# Builds a one-commit temp repo, captures BEFORE, then runs the case-specific script,
# then calls check_frozen_paths and prints the result.
_HARNESS_TEMPLATE = """\
source scripts/expand_loop.sh
flag_for_human() {{ echo "FLAG: $*"; }}
log() {{ :; }}

TEMP_REPO=$(mktemp -d)
cd "$TEMP_REPO" || exit 1
git init -q
git config user.email "test@example.com"
git config user.name "Test"
echo "init" > init.txt
git add -A
git commit -q -m "init"
BEFORE=$(git rev-parse HEAD)

{case_script}

check_frozen_paths PHASE T21.4 "$BEFORE"
echo "rc=$? head=$(git rev-parse HEAD) before=$BEFORE"
"""

# Separate harness for the history-rewrite case: needs two baseline commits so that
# resetting to the first makes BEFORE a non-ancestor of HEAD.
_HARNESS_HISTORY_REWRITE = """\
source scripts/expand_loop.sh
flag_for_human() { echo "FLAG: $*"; }
log() { :; }

TEMP_REPO=$(mktemp -d)
cd "$TEMP_REPO" || exit 1
git init -q
git config user.email "test@example.com"
git config user.name "Test"

echo "root" > root.txt
git add -A
git commit -q -m "root"
ROOT_SHA=$(git rev-parse HEAD)

echo "before" > before.txt
git add -A
git commit -q -m "before"
BEFORE=$(git rev-parse HEAD)

# Session: makes a commit then force-resets to ROOT_SHA (before BEFORE).
echo "session" > session.txt
git add -A
git commit -q -m "session"
git reset -q --hard "$ROOT_SHA"

check_frozen_paths PHASE T21.4 "$BEFORE"
echo "rc=$? head=$(git rev-parse HEAD) before=$BEFORE"
"""


def _run_harness(harness: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run a bash harness from _REPO_ROOT and return the completed process."""
    return subprocess.run(
        [str(_GIT_BASH), "-c", harness],
        cwd=_REPO_ROOT,
        env={**os.environ, "PY_RUN": "true"},
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _parse_result(result: subprocess.CompletedProcess[str]) -> tuple[int, str, str]:
    """Return (rc, head, before) from the harness output line 'rc=N head=H before=B'."""
    for line in result.stdout.splitlines():
        if line.startswith("rc="):
            parts = line.split()
            rc = int(parts[0].split("=", 1)[1])
            head = parts[1].split("=", 1)[1]
            before = parts[2].split("=", 1)[1]
            return rc, head, before
    pytest.fail(
        f"harness did not print rc=: stdout={result.stdout!r} stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Case 1: commit to evals/calibration/ → halts and resets HEAD
# ---------------------------------------------------------------------------

_CASE_CALIBRATION = """\
mkdir -p evals/calibration
echo "x" > evals/calibration/x.jsonl
git add -A
git commit -q -m "bad: frozen calibration path"
"""


def test_frozen_calibration_path_halts_and_resets() -> None:
    """A session committing to evals/calibration/ triggers check_frozen_paths to return 2
    and reset HEAD back to before the session."""
    harness = _HARNESS_TEMPLATE.format(case_script=_CASE_CALIBRATION)
    result = _run_harness(harness)

    rc, head, before = _parse_result(result)

    assert rc == 2, f"expected return 2 (frozen hit), got {rc}"
    assert "FLAG" in result.stdout, f"expected flag_for_human call: {result.stdout!r}"
    assert head == before, f"HEAD was not reset: head={head} before={before}"


# ---------------------------------------------------------------------------
# Case 2: commit to tests/ only → allowed (returns 0)
# ---------------------------------------------------------------------------

_CASE_TESTS_ONLY = """\
mkdir -p tests
echo "x" > tests/x.py
git add -A
git commit -q -m "ok: tests path is not frozen"
"""


def test_tests_path_is_allowed() -> None:
    """A session committing only to tests/ does not hit the frozen list; check returns 0."""
    harness = _HARNESS_TEMPLATE.format(case_script=_CASE_TESTS_ONLY)
    result = _run_harness(harness)

    rc, _head, _before = _parse_result(result)

    assert rc == 0, f"expected return 0 (tests path allowed), got {rc}"
    assert "FLAG" not in result.stdout, (
        f"unexpected flag_for_human call: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Case 3: history rewrite (reset to before BEFORE) → halts
# ---------------------------------------------------------------------------


def test_history_rewrite_halts() -> None:
    """If the session resets HEAD so BEFORE is no longer an ancestor, the check halts."""
    result = _run_harness(_HARNESS_HISTORY_REWRITE)

    rc, _head, _before = _parse_result(result)

    assert rc == 2, f"expected return 2 (history rewrite), got {rc}"
    assert "FLAG" in result.stdout, (
        f"expected flag_for_human call: {result.stdout!r}"
    )
