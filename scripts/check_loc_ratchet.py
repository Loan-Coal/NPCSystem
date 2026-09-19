#!/usr/bin/env python
"""
Module: check_loc_ratchet
Layer: harness (repo-level dev tool, outside the package layer model)
Purpose: Reverse LOC ratchet — counts non-test Python LOC across
         src/npc_engine/, scripts/, evals/ and demo_game/, compares the
         aggregate total to scripts/loc_baseline.txt, and fails if the total
         rose. Moving logic between tracked directories is visible rather than
         free: all four per-directory counts are reported on every run.
         Rules 1 and 6. Findings: L10 dead-surface sweep.
Dependencies: stdlib only (argparse, pathlib, sys).
Used by: `make check-loc-ratchet`, scripts/loop_gates.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASELINE_REL = Path("scripts/loc_baseline.txt")

# Directories counted. Changing this list requires bumping the baseline.
_TRACKED_DIRS: tuple[str, ...] = (
    "src/npc_engine",
    "scripts",
    "evals",
    "demo_game",
)


# ---------------------------------------------------------------------------
# LOC counting
# ---------------------------------------------------------------------------


def _is_test_file(rel_parts: tuple[str, ...]) -> bool:
    """Return True if any path segment is a test directory or a test file."""
    for part in rel_parts:
        if part in ("tests", "test"):
            return True
    filename = rel_parts[-1] if rel_parts else ""
    return filename.startswith("test_")


def count_loc_for_dir(root: Path, tracked_dir: str) -> int:
    """Count non-test Python LOC in tracked_dir relative to root."""
    target = root / tracked_dir
    if not target.exists():
        return 0
    total = 0
    for py_file in sorted(target.rglob("*.py")):
        rel_parts = py_file.relative_to(root).parts
        if "__pycache__" in rel_parts:
            continue
        if _is_test_file(rel_parts):
            continue
        try:
            total += len(py_file.read_text(encoding="utf-8", errors="ignore").splitlines())
        except OSError:
            pass
    return total


def count_all(root: Path) -> dict[str, int]:
    """Return {dir: loc, ..., 'total': sum} for all tracked directories."""
    counts: dict[str, int] = {}
    for tracked in _TRACKED_DIRS:
        counts[tracked] = count_loc_for_dir(root, tracked)
    counts["total"] = sum(counts[d] for d in _TRACKED_DIRS)
    return counts


# ---------------------------------------------------------------------------
# Baseline I/O
# ---------------------------------------------------------------------------


def read_baseline(baseline_path: Path) -> dict[str, int]:
    """Parse the baseline file into {key: int}.

    Lines beginning with '#' are comments.  Every other non-blank line must
    have the form ``key: value``.
    """
    if not baseline_path.exists():
        return {}
    result: dict[str, int] = {}
    for raw in baseline_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val_str = val.strip()
        if not val_str.isdigit():
            continue
        result[key] = int(val_str)
    return result


def write_baseline(baseline_path: Path, counts: dict[str, int]) -> None:
    """Overwrite the baseline file with current counts (--update mode)."""
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# LOC ratchet baseline — do not edit by hand.",
        "# Raise the total with a reason in the commit message.",
        "# Budgeted allowance: +700 LOC for T12.1 (~400 scripts gate script),",
        "#   T15.1 (~200 src/npc_engine scheduler+metrics), T16.2 (~100 src metrics).",
        "# T15.1 and T16.2 list this file in their Files: and will bump it when they land.",
        "#",
    ]
    for tracked in _TRACKED_DIRS:
        lines.append(f"{tracked}: {counts[tracked]}")
    lines.append(f"total: {counts['total']}")
    baseline_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------


def _validate_baseline(baseline: dict[str, int], baseline_path: Path) -> str | None:
    """Return an error message if the baseline is invalid, else None."""
    if not baseline:
        return (
            f"Baseline file not found or empty: {baseline_path}\n"
            "  Run: python scripts/check_loc_ratchet.py --update"
        )
    if baseline.get("total") is None:
        return (
            f"Baseline file {baseline_path} has no 'total:' entry"
            " — regenerate with --update."
        )
    return None


def check_loc_ratchet(
    root: Path | None = None,
    baseline_path: Path | None = None,
) -> list[str]:
    """Run the LOC ratchet check; return failure messages (empty = green)."""
    if root is None:
        root = _REPO_ROOT
    if baseline_path is None:
        baseline_path = root / _BASELINE_REL

    current = count_all(root)
    baseline = read_baseline(baseline_path)

    err = _validate_baseline(baseline, baseline_path)
    if err:
        return [err]

    baseline_total = baseline["total"]
    current_total = current["total"]
    if current_total > baseline_total:
        delta = current_total - baseline_total
        return [
            f"LOC total rose by {delta}: {current_total} > baseline {baseline_total}\n"
            "  Either delete code or raise the baseline with a reason in the commit message."
        ]
    return []


# ---------------------------------------------------------------------------
# Entry point helpers
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Reverse LOC ratchet — fail if non-test Python LOC total rose."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_REPO_ROOT,
        help="Repo root to scan (default: repo root derived from this file's location).",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Overwrite scripts/loc_baseline.txt with current counts.",
    )
    return parser


def _print_counts(current: dict[str, int]) -> None:
    """Print per-directory and total LOC counts."""
    print("LOC counts (non-test Python):")
    for tracked in _TRACKED_DIRS:
        print(f"  {tracked}: {current[tracked]}")
    print(f"  total: {current['total']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns 0 on green, 1 on red."""
    args = _build_parser().parse_args(argv)
    root: Path = args.root
    baseline_path = root / _BASELINE_REL
    current = count_all(root)
    _print_counts(current)

    if args.update:
        write_baseline(baseline_path, current)
        print(f"\nBaseline updated: {baseline_path}")
        return 0

    failures = check_loc_ratchet(root=root, baseline_path=baseline_path)
    if failures:
        print("\nFAIL:")
        for msg in failures:
            print(f"  {msg}")
        return 1

    baseline = read_baseline(baseline_path)
    baseline_total = baseline.get("total", 0)
    headroom = baseline_total - current["total"]
    print(f"\nOK — {headroom} LOC headroom before the ratchet fires.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
