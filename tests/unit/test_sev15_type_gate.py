"""
Regression test for SEV-15 — mypy must stay at 0 errors (hard gate).

Ensures 'make type' can be a hard CI gate now that SEV-14 achieved 0 errors.
"""

from __future__ import annotations

import subprocess
import sys


def test_mypy_exits_zero() -> None:
    """mypy src/ must exit 0 — any new type error breaks this gate."""
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "src/", "--no-error-summary"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"mypy found errors — 'make type' gate would fail:\n{result.stdout}{result.stderr}"
    )
