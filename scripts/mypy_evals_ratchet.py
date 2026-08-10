#!/usr/bin/env python
"""
Module: mypy_evals_ratchet
Layer: harness (repo-level dev tool)
Purpose: Gate the mypy error count in evals/ against a baseline that can only shrink.
Dependencies: stdlib + mypy (already a dev dependency).
Used by: `make type-evals`, CI static-analysis.

Mirrors mypy_ratchet.py but targets evals/ instead of src/.
Baseline is stored in .mypy_evals_baseline (integer line count).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / ".mypy_evals_baseline"

_FOUND_RE = re.compile(r"Found (\d+) error")
_SUCCESS_RE = re.compile(r"Success: no issues")


def _run_mypy() -> int:
    """Run `mypy evals/` and return the reported error count (0 on success)."""
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", "evals/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    if _SUCCESS_RE.search(out):
        return 0
    match = _FOUND_RE.search(out)
    if match:
        return int(match.group(1))
    sys.stderr.write(out)
    raise SystemExit("mypy_evals_ratchet: could not parse mypy output (see above).")


def _read_baseline() -> int:
    """Read the committed baseline error count (missing file ⇒ 0, i.e. strictest)."""
    if not BASELINE_PATH.exists():
        return 0
    return int(BASELINE_PATH.read_text(encoding="utf-8").strip() or "0")


def main() -> int:
    """Run the ratchet. Exit 1 if the error count rose above the baseline."""
    parser = argparse.ArgumentParser(description="Ratchet mypy error count for evals/ (monotonically non-increasing).")
    parser.add_argument("--update", action="store_true", help="Write the current count as the new baseline.")
    args = parser.parse_args()

    current = _run_mypy()
    if args.update:
        BASELINE_PATH.write_text(f"{current}\n", encoding="utf-8")
        print(f"mypy-evals-ratchet: baseline set to {current}.")
        return 0

    baseline = _read_baseline()
    if current > baseline:
        print(
            f"mypy-evals-ratchet: FAIL - {current} type errors > baseline {baseline}. "
            f"Fix the new errors (run `make type-evals` to see them)."
        )
        return 1
    if current < baseline:
        print(
            f"mypy-evals-ratchet: {current} < baseline {baseline} - ratchet down! "
            f"Run `make type-evals-update` to lock in the win."
        )
        return 0
    print(f"mypy-evals-ratchet: OK - {current} type errors (== baseline).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
