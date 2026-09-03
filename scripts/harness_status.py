#!/usr/bin/env python
"""
Module: harness_status
Layer: scripts (dev tooling)
Purpose: Print every gate and baseline the harness enforces, read live from the files
         that hold them, so no document has to keep a copy of a number.
Does NOT: run a gate, change a baseline, or fail on any value it reports.
Dependencies: pathlib, re, sys
Dependencies injected: None.
Used by: make harness-status, project-harness/HARNESS_GATES.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = REPO_ROOT / "Makefile"

# (label, path, kind) — "lines" counts non-comment non-blank rows, "value" reads one number.
BASELINES: tuple[tuple[str, str, str], ...] = (
    ("CLAUDE.md rule violations (src/, scripts/)", "scripts/rules_baseline.txt", "lines"),
    ("CLAUDE.md rule violations (evals/)", "scripts/evals_baseline.txt", "lines"),
    ("known-failing integration tests", "scripts/integration_baseline.txt", "lines"),
    ("mypy errors (src/)", ".mypy_baseline", "value"),
    ("mypy errors (demo_game/)", ".mypy_baseline_demo", "value"),
    ("engine log sites without duration_ms", "scripts/engine_logs_baseline.txt", "value"),
    ("assertion-free tests", "scripts/check_test_quality_baseline.txt", "value"),
    ("dead eval keywords", "scripts/dead_keywords_baseline.txt", "value"),
)


def _read_lines(path: Path) -> str:
    """Return the count of meaningful rows in a list-style baseline file."""
    if not path.exists():
        return "MISSING"
    rows = [r for r in path.read_text(encoding="utf-8").splitlines() if r.strip() and not r.lstrip().startswith("#")]
    return str(len(rows))


def _read_value(path: Path) -> str:
    """Return the single number held in a count-style baseline file."""
    if not path.exists():
        return "MISSING"
    return path.read_text(encoding="utf-8").strip() or "EMPTY"


def check_targets() -> list[str]:
    """Return the targets `make check` runs, in order, read from the Makefile.

    Returns:
        Target names; empty when the Makefile has no `check:` rule.
    """
    match = re.search(r"^check:(.*)$", MAKEFILE.read_text(encoding="utf-8"), re.M)
    return match.group(1).split() if match else []


def report() -> str:
    """Return the full status block as text.

    Returns:
        A printable report of `make check`'s targets and every baseline's live value.
    """
    targets = check_targets()
    lines = [f"make check runs {len(targets)} targets:"]
    lines += [f"  - {name}" for name in targets]
    lines.append("")
    lines.append("Baselines (a gate fails only on a NEW violation; these may shrink, never grow):")
    width = max(len(label) for label, _, _ in BASELINES)
    for label, rel, kind in BASELINES:
        path = REPO_ROOT / rel
        value = _read_lines(path) if kind == "lines" else _read_value(path)
        lines.append(f"  {label.ljust(width)}  {value.rjust(5)}   {rel}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Print the report.

    Args:
        argv: Unused; present for a uniform script entry point.

    Returns:
        Always 0 — this reports, it does not gate.
    """
    print(report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
