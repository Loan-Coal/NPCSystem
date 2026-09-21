"""
Module: test_mypy_ratchet
Layer: test (unit)
Purpose: Pin the mypy ratchet's comparison and baseline I/O, including the parameterised
         target/baseline/label seam that lets one script serve src/ and demo_game/ (R2.2).
Dependencies: pytest, pathlib; scripts/mypy_ratchet.py
Used by: pytest (make test / make check)

Why this exists: the ratchet is the only thing standing between demo_game/'s 256 type
errors and silent growth, and its RED direction had never been asserted anywhere. The
comparison is driven with synthetic counts so the test needs no mypy run — a test that
shelled out to mypy would take minutes and would drift with the real error count.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from mypy_ratchet import (  # noqa: E402
    compare,
    read_baseline,
)

_LABEL = "mypy-demo-ratchet"
_HINT = "make type-demo-update"


def test_a_risen_count_fails() -> None:
    """One more error than the baseline is a regression and must exit non-zero."""
    assert compare(257, 256, _LABEL, _HINT) == 1


def test_an_equal_count_passes() -> None:
    """Matching the baseline is the steady state."""
    assert compare(256, 256, _LABEL, _HINT) == 0


def test_a_fallen_count_passes_and_advises_an_update(capsys) -> None:
    """Debt shrinking must not fail the build, but must nag for a re-record."""
    assert compare(255, 256, _LABEL, _HINT) == 0
    assert _HINT in capsys.readouterr().out


def test_the_failure_message_names_both_counts(capsys) -> None:
    """A red ratchet has to say what rose and from where, or it cannot be acted on."""
    compare(300, 256, _LABEL, _HINT)
    out = capsys.readouterr().out
    assert "300" in out and "256" in out and _LABEL in out


def test_a_missing_baseline_reads_as_zero(tmp_path: Path) -> None:
    """No baseline file means strictest, not 'anything goes' — any error is then new."""
    assert read_baseline(tmp_path / "nonexistent") == 0


def test_baseline_is_read_as_a_bare_integer(tmp_path: Path) -> None:
    """The baseline format is one integer plus a newline, like .mypy_baseline."""
    path = tmp_path / ".mypy_baseline_demo"
    path.write_text("256\n", encoding="utf-8")
    assert read_baseline(path) == 256


def test_the_demo_baseline_file_holds_an_integer() -> None:
    """The committed demo baseline must parse, or `make type-demo` cannot run."""
    assert read_baseline(_REPO_ROOT / ".mypy_baseline_demo") > 0
