#!/usr/bin/env python
"""
Module: mypy_ratchet
Layer: harness (repo-level dev tool)
Purpose: Gate a directory's mypy error count against a baseline that can only shrink.
Dependencies: stdlib + mypy (already a dev dependency).
Used by: `make type-ratchet` (src/), `make type-demo` (demo_game/), CI.

`make type` cannot be flipped to gating while errors exist, so it would simply be
dropped from CI (which is exactly how the debt accumulated invisibly). This ratchet
runs mypy, parses the error count, and FAILS only if the count rose above the committed
baseline. When the count drops, it reports the win and (with --update) lowers the
baseline. Net effect: type errors are monotonically non-increasing on every merge.

The target directory, baseline file and label are parameters rather than constants
(R2.2): `mypy_ratchet.py` and `mypy_evals_ratchet.py` were byte-identical but for four
fields, and `demo_game/` would have been a third copy of the same 83 lines. Defaults
reproduce the original `src/` behaviour exactly, so `make type-ratchet` is unchanged.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / ".mypy_baseline"

DEFAULT_TARGET = "src/"
DEFAULT_BASELINE = ".mypy_baseline"
DEFAULT_LABEL = "mypy-ratchet"
DEFAULT_UPDATE_HINT = "make type-ratchet-update"

_FOUND_RE = re.compile(r"Found (\d+) error")
_SUCCESS_RE = re.compile(r"Success: no issues")


def run_mypy(target: str = DEFAULT_TARGET, label: str = DEFAULT_LABEL) -> int:
    """Run `mypy <target>` and return the reported error count (0 on success).

    Args:
        target: Directory to type-check, as mypy would receive it.
        label: Prefix used when mypy's output cannot be parsed.
    Returns:
        The error count mypy reported.
    Raises:
        SystemExit: If mypy printed neither a count nor a success line.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", target],
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
    # mypy produced neither a count nor a success line - surface its output and fail loud.
    sys.stderr.write(out)
    raise SystemExit(f"{label}: could not parse mypy output (see above).")


def read_baseline(path: Path = BASELINE_PATH) -> int:
    """Read a committed baseline error count (missing file ⇒ 0, i.e. strictest)."""
    if not path.exists():
        return 0
    return int(path.read_text(encoding="utf-8").strip() or "0")


def compare(current: int, baseline: int, label: str, update_hint: str) -> int:
    """Report a ratchet comparison and return its exit code.

    Args:
        current: Error count just measured.
        baseline: Committed baseline count.
        label: Human-readable gate name for the printed messages.
        update_hint: The make target that would re-record the baseline.
    Returns:
        1 when the count rose above the baseline, else 0.
    """
    if current > baseline:
        print(f"{label}: FAIL - {current} type errors > baseline {baseline}. "
              f"Fix the new errors (run mypy directly to see them).")
        return 1
    if current < baseline:
        print(f"{label}: {current} < baseline {baseline} - ratchet down! "
              f"Run `{update_hint}` to lock in the win.")
        return 0
    print(f"{label}: OK - {current} type errors (== baseline).")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ratchet a directory's mypy error count (monotonically non-increasing)."
    )
    parser.add_argument("--update", action="store_true",
                        help="Write the current count as the new baseline.")
    parser.add_argument("--target", default=DEFAULT_TARGET,
                        help=f"Directory to type-check (default: {DEFAULT_TARGET}).")
    parser.add_argument("--baseline-file", default=DEFAULT_BASELINE,
                        help=f"Baseline file, repo-relative (default: {DEFAULT_BASELINE}).")
    parser.add_argument("--label", default=DEFAULT_LABEL,
                        help=f"Name used in output (default: {DEFAULT_LABEL}).")
    parser.add_argument("--update-hint", default=DEFAULT_UPDATE_HINT,
                        help="Make target quoted when the count drops.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the ratchet. Exit 1 if the error count rose above the baseline."""
    args = _parse_args(argv)
    baseline_path = REPO_ROOT / args.baseline_file

    current = run_mypy(args.target, args.label)
    if args.update:
        baseline_path.write_text(f"{current}\n", encoding="utf-8")
        print(f"{args.label}: baseline set to {current}.")
        return 0

    return compare(current, read_baseline(baseline_path), args.label, args.update_hint)


if __name__ == "__main__":
    raise SystemExit(main())
