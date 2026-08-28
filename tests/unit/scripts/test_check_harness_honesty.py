"""
Module: tests.unit.scripts.test_check_harness_honesty
Layer: tests
Purpose: Unit tests for scripts/check_harness_honesty.py — R1.4 RED anchor (H3 deleted,
         ordering defect fixed) plus H1/H2 behavioural coverage.
Dependencies: sys, pathlib, pytest, check_harness_honesty
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import check_harness_honesty  # noqa: E402
from check_harness_honesty import main  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_harness_honesty.py"


# ---------------------------------------------------------------------------
# RED anchor — must fail before R1.4 lands
# ---------------------------------------------------------------------------


def test_h3_is_absent_from_check_harness_honesty() -> None:
    """H3 (NEXT_SESSION.md check) was deleted in R1.4 — it read an archived path.

    grep -c H3 scripts/check_harness_honesty.py must return 0 after the task.
    """
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "H3" not in source, (
        "H3 check is still present in check_harness_honesty.py — R1.4 requires it deleted"
    )


# ---------------------------------------------------------------------------
# H1 behavioural tests — hard gate must still fire
# ---------------------------------------------------------------------------


def _run_main(
    *,
    lint_clean: bool,
    mypy_count: int,
    open_blocks: list[str],
    strict: bool = False,
) -> int:
    """Run main() with mocked infrastructure helpers."""
    argv = ["--strict"] if strict else []
    with (
        patch.object(check_harness_honesty, "_lint_clean", return_value=lint_clean),
        patch.object(check_harness_honesty, "_mypy_baseline_count", return_value=mypy_count),
        patch.object(check_harness_honesty, "_open_issue_blocks", return_value=open_blocks),
        patch("subprocess.run") as mock_sub,
    ):
        # H2 subprocess.run (git status) — return clean tree by default
        mock_sub.return_value.returncode = 0
        mock_sub.return_value.stdout = ""
        return main(argv)


def test_h1_fires_when_lint_dirty_and_no_covering_issue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """H1 exits 1 when lint is red and no open ISSUE mentions lint/ruff."""
    result = _run_main(lint_clean=False, mypy_count=0, open_blocks=[])
    assert result == 1
    assert "H1" in capsys.readouterr().out


def test_h1_silent_when_lint_dirty_but_issue_covers_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """H1 does not fire when lint is red but a ticket already names it."""
    issue = "ISSUE-999: ruff lint failures in demo_game — not fixing now\nSeverity: P3\n"
    result = _run_main(lint_clean=False, mypy_count=0, open_blocks=[issue])
    assert result == 0
    assert "H1" not in capsys.readouterr().out


def test_h1_fires_when_mypy_nonzero_and_no_covering_issue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """H1 exits 1 when mypy baseline > 0 and no open ISSUE mentions mypy."""
    result = _run_main(lint_clean=True, mypy_count=3, open_blocks=[])
    assert result == 1
    assert "H1" in capsys.readouterr().out


def test_h1_passes_when_lint_and_mypy_clean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """H1 exits 0 when lint is clean and mypy baseline is 0."""
    result = _run_main(lint_clean=True, mypy_count=0, open_blocks=[])
    assert result == 0


# ---------------------------------------------------------------------------
# H3 gone — next-session mismatch must NOT produce any output
# ---------------------------------------------------------------------------


def test_next_session_mismatch_produces_no_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """After H3 deletion, a NEXT_SESSION/ISSUES mismatch is silently ignored.

    Previously this would print a WARN [H3] line. Now it must not.
    """
    issue = "ISSUE-001: something open\n"
    result = _run_main(lint_clean=True, mypy_count=0, open_blocks=[issue])
    out = capsys.readouterr().out
    assert "H3" not in out
    assert result == 0


# ---------------------------------------------------------------------------
# --strict flag covers H2 only (not H3 which is gone)
# ---------------------------------------------------------------------------


def test_strict_help_text_does_not_mention_h3() -> None:
    """--strict help text must not reference H3 after it is deleted."""
    import argparse

    parser = argparse.ArgumentParser()
    # Re-invoke via source inspection — the --strict action's help string must not say H3.
    source = _SCRIPT.read_text(encoding="utf-8")
    # Find the --strict add_argument call and check its help text
    assert "H3" not in source, "--strict description still mentions H3"
