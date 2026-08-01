"""
Module: loop_gates
Layer: harness
Purpose: Gate sub-check definitions and gate-gaming frozen paths — THE ONE FILE TO EDIT
    when the project's gate changes.
Dependencies: stdlib only (sys, pathlib).
Used by: scripts/classify_gate_failure.py, gate_baseline.py, gate_confirm.py, scan_fix_diff.py.

`make check` is a single pass/fail command, which is not enough for an unattended loop:
when it goes red the loop must decide whether the failure is *auto-fixable* (form) or
*HALT-class* (behaviour). To decide, it re-runs the gate's constituents individually.

Classification rule:
  HALT-class    — asserts *behaviour*. A red test means the code is wrong; a repair
                  session would be guessing at intent, and the easiest way to make a red
                  test green is to edit the test, which is fraud. Escalate to a human.
  AUTOFIX-class — asserts *form*. Lint, types, docstrings and structural rules have
                  mechanical, verifiable fixes, so one bounded repair attempt is safe.

HALT checks run first, so reaching the AUTOFIX phase proves every test is already green.

Why AUTOFIX entries shell out to ``make`` instead of naming ruff/mypy directly: the
roadmap explicitly plans to rewrite these targets (EVAL-P0.3 widens `lint` to `evals/`;
EVAL-P6.3 rewrites seven targets). Naming the underlying commands here would silently
drift out of step with the real gate the moment those tasks land.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def python_executable() -> str:
    """Path to the interpreter the gate should use (mirrors the Makefile's PYTHON)."""
    venv = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv.exists():
        return str(venv)
    posix_venv = REPO_ROOT / ".venv" / "bin" / "python"
    if posix_venv.exists():
        return str(posix_venv)
    return sys.executable


# The full gate, exactly as a human runs it. Its verdict is authoritative; the specs
# below exist only to explain a red verdict, never to replace it.
FULL_GATE_CMD: tuple[str, ...] = ("make", "check")

# Behaviour checks. Run first; any failure is HALT-class and is never auto-repaired.
# Coverage is deliberately NOT duplicated here — `make check` already enforces
# --cov-fail-under=80, and re-running the suite with coverage would double a 144 s gate.
# A red `make check` with every constituent green is attributed to coverage by
# classify_gate_failure.py and treated as HALT-class.
HALT_CHECK_SPECS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tests", (python_executable(), "-m", "pytest", "tests/", "-q", "--tb=no", "-rf")),
)

# Form checks. One bounded /fix-make-failure session is allowed per red gate.
AUTOFIX_CHECK_SPECS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lint", ("make", "lint")),
    ("check-rules", ("make", "check-rules")),
    ("check-layers", ("make", "check-layers")),
    ("check-docstrings", ("make", "check-docstrings")),
    ("type", ("make", "type")),
    ("check-harness", ("make", "check-harness")),
)

# Run only when a task touched demo_game/ (the project's own rule).
DEMO_GATE_CMD: tuple[str, ...] = ("make", "test-demo")
DEMO_PATH_PREFIX = "demo_game/"

# --- gate-gaming defences -----------------------------------------------------------
# Paths a repair session must never touch. Editing any of these can make a red gate green
# without fixing anything.
#
# `scripts/rules_baseline.txt` is the one unique to this repo and the most dangerous:
# `make check-rules-update` legitimately rewrites it, so a repair session that runs the
# update target launders every new violation into "expected" and the gate goes green
# having fixed precisely nothing. The upstream kit has no ratchet and so no equivalent.
FROZEN_PATH_PREFIXES: tuple[str, ...] = (
    "tests/",
    "demo_game/tests/",
    "e2e/",
    ".github/",
    "scripts/rules_baseline.txt",
    "scripts/check_rules.py",
    "scripts/check_layers.py",
    "scripts/check_harness_honesty.py",
    "scripts/docstring_audit.py",
    "scripts/mypy_ratchet.py",
    "scripts/loop_gates.py",
    "scripts/classify_gate_failure.py",
    "scripts/gate_baseline.py",
    "scripts/gate_attribution.py",
    "scripts/gate_confirm.py",
    "scripts/scan_fix_diff.py",
    "scripts/roadmap_cursor.py",
    "scripts/_roadmap_cursor_core.py",
    "scripts/expand_loop.sh",
    "scripts/loop_compat.sh",
    "scripts/loop.config.sh",
    "Makefile",
    "pyproject.toml",
    "mypy.ini",
    "conftest.py",
)

# Added lines matching these read as suppressing a check rather than satisfying it.
SUPPRESSION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("noqa", r"#\s*noqa"),
    ("type-ignore", r"#\s*type:\s*ignore"),
    ("swallowed-except", r"except[^:]*:\s*(pass|\.\.\.)\s*$"),
    ("bare-except", r"except\s*:\s*$"),
    ("skip-marker", r"@pytest\.mark\.(skip|xfail)"),
    ("runtime-skip", r"pytest\.skip\("),
    ("coverage-threshold", r"--cov-fail-under"),
    ("ratchet-update", r"--update-baseline|--update\b"),
    ("mypy-silence", r"disallow_untyped_defs\s*=\s*False|ignore_errors\s*=\s*True"),
    ("ruff-disable", r"per-file-ignores|extend-ignore"),
)

BASELINE_FILE = "project-harness/.loop-state/gate_baseline.json"
