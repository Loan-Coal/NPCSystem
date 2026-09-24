"""
Module: test_expand_loop_execution_error
Layer: test (unit)
Purpose: Pin that expand_loop.sh retries a task once when its session log holds only
    the CLI's bare "Execution error", and halts as before if the retry fails too (ISSUE-370).
Does NOT: launch claude, touch the roadmap, or run the loop's preflight.
Dependencies: scripts/expand_loop.sh (sourced, its `main` guarded), Git Bash.
Used by: pytest (make test / make check)

Why this exists: on 2026-09-21 T14.1's session printed only "Execution error" and exited
after 14 s. That matched neither a status token nor the usage-limit pattern, so the loop
halted the night on what was a transient CLI failure. The harness sources the script,
stubs the claude session to replay canned logs, and calls run_one_task directly.
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

# Sources the script (no `main`), replays call<N>.log as the Nth claude session's log,
# then runs one task and reports its return code, how many sessions ran, and any flag.
_HARNESS = r"""
source scripts/expand_loop.sh
CALLS=0
run_claude_session() {
  CALLS=$((CALLS + 1))
  cp "$SEQ_DIR/call$CALLS.log" "$1"
  return 0
}
flag_for_human() { echo "FLAG: $1"; }
log() { :; }
run_one_task PHASE TASK
echo "rc=$? calls=$CALLS"
"""


def _run_task(tmp_path: Path, session_logs: list[str]) -> str:
    """Replay session_logs as consecutive claude sessions and return the harness output."""
    for index, content in enumerate(session_logs, start=1):
        (tmp_path / f"call{index}.log").write_text(content, encoding="utf-8")
    env = {
        **os.environ,
        "SEQ_DIR": tmp_path.as_posix(),
        "LOOP_LOG_DIR": (tmp_path / "logs").as_posix(),
        "LOOP_STATE_DIR": (tmp_path / "state").as_posix(),
        "PY_RUN": "true",
        "TRANSIENT_RETRY_SLEEP_SECS": "0",
    }
    (tmp_path / "logs").mkdir()
    (tmp_path / "state").mkdir()
    done = subprocess.run(
        [str(_GIT_BASH), "-c", _HARNESS],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "rc=" in done.stdout, f"harness did not finish: {done.stdout!r} {done.stderr!r}"
    return done.stdout


def test_bare_execution_error_is_retried_once_and_the_retry_can_succeed(tmp_path: Path) -> None:
    """A first session that printed only "Execution error" is re-run, and its token counts."""
    out = _run_task(tmp_path, ["Execution error\n", "AUTO_STATUS: TASK_COMPLETE\n"])

    assert "rc=0 calls=2" in out
    assert "FLAG" not in out


def test_two_bare_execution_errors_halt_as_before(tmp_path: Path) -> None:
    """The retry is single: a second bare "Execution error" flags a human and halts (rc 2)."""
    out = _run_task(tmp_path, ["Execution error\n", "Execution error\n"])

    assert "rc=2 calls=2" in out
    assert "FLAG: no status token from task TASK" in out


def test_a_log_with_other_content_is_not_retried(tmp_path: Path) -> None:
    """Only a log that holds nothing but "Execution error" is transient; anything else halts."""
    out = _run_task(tmp_path, ["Execution error\nTraceback: something real broke\n"])

    assert "rc=2 calls=1" in out
    assert "FLAG: no status token from task TASK" in out


def test_a_session_with_a_token_is_never_retried(tmp_path: Path) -> None:
    """A normal status token takes the existing path with exactly one session."""
    out = _run_task(tmp_path, ["work\nAUTO_STATUS: TASK_COMPLETE\n"])

    assert "rc=0 calls=1" in out
