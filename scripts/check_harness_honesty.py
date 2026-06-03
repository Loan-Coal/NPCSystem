#!/usr/bin/env python
"""
Module: check_harness_honesty
Layer: harness (repo-level dev tool)
Purpose: Fail when known debt is not logged as a ticket, or the docs claim a clean
         state the gates contradict.
Dependencies: stdlib + ruff (dev dep).
Used by: `make check-harness`, pre-commit, CI.

Policy: every red gate must be tracked by an OPEN ticket in project-harness/ISSUES.md.
  H1 (hard)  - lint is red or the mypy baseline is non-zero, but no open ISSUE covers it.
  H2 (warn)  - ROADMAP marks a phase "complete" while relevant files are untracked.
  H3 (warn)  - ISSUES.md has open tickets but NEXT_SESSION.md claims none.
H2/H3 are advisory by default; --strict makes them fail too.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ISSUES = REPO_ROOT / "project-harness" / "ISSUES.md"
NEXT_SESSION = REPO_ROOT / "project-harness" / "NEXT_SESSION.md"
ROADMAP = REPO_ROOT / "project-harness" / "ROADMAP.md"
MYPY_BASELINE = REPO_ROOT / ".mypy_baseline"

_NO_OPEN_ISSUES_RE = re.compile(r"open issues.{0,80}?\bnone\b", re.IGNORECASE | re.DOTALL)


def _read(path: Path) -> str:
    """Read a repo file as UTF-8 (empty string if missing)."""
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _lint_clean() -> bool:
    """True if `ruff check src/` reports no errors."""
    proc = subprocess.run([sys.executable, "-m", "ruff", "check", "src/"],
                          cwd=REPO_ROOT, capture_output=True, text=True)
    return proc.returncode == 0


def _mypy_baseline_count() -> int:
    """Committed mypy baseline error count (0 if absent)."""
    if not MYPY_BASELINE.exists():
        return 0
    return int(MYPY_BASELINE.read_text(encoding="utf-8").strip() or "0")


def _open_issue_blocks() -> list[str]:
    """Text of each OPEN issue in ISSUES.md (heading `## ISSUE-N`, no [FIXED]/[WONTFIX])."""
    blocks = re.split(r"(?m)^## ", _read(ISSUES))
    return [b for b in blocks if re.match(r"ISSUE-\d+:", b)]


def _covered(blocks: list[str], keywords: tuple[str, ...]) -> bool:
    """True if any open issue block mentions one of the keywords."""
    haystack = "\n".join(blocks).lower()
    return any(kw in haystack for kw in keywords)


def main() -> int:
    """Run the honesty checks. Exit 1 on any hard (H1) gap, or any check when --strict."""
    parser = argparse.ArgumentParser(description="Fail when debt is untracked or docs contradict the gates.")
    parser.add_argument("--strict", action="store_true", help="Treat H2/H3 warnings as failures too.")
    args = parser.parse_args()

    failed = False
    warned = False
    open_blocks = _open_issue_blocks()

    # H1 - every red gate needs a covering open ticket.
    gaps: list[str] = []
    if not _lint_clean() and not _covered(open_blocks, ("lint", "ruff")):
        gaps.append("`make lint` is red but no open ISSUE mentions lint/ruff")
    mypy_count = _mypy_baseline_count()
    if mypy_count > 0 and not _covered(open_blocks, ("mypy", "type error", "type errors", "type gate")):
        gaps.append(f"{mypy_count} mypy errors (baseline) but no open ISSUE mentions mypy/type errors")
    if gaps:
        print("check-harness: FAIL [H1] - known debt is not logged as a ticket in ISSUES.md:")
        for g in gaps:
            print(f"    - {g}")
        print("  Log it as the next ISSUE-NNN (policy: debt must be a ticket).")
        failed = True

    # H3 - ISSUES.md has open tickets but NEXT_SESSION claims none.
    if open_blocks and _NO_OPEN_ISSUES_RE.search(_read(NEXT_SESSION)):
        tag = "FAIL" if args.strict else "WARN"
        ids = ", ".join(sorted(re.match(r"(ISSUE-\d+)", b).group(1) for b in open_blocks))
        print(f"check-harness: {tag} [H3] - ISSUES.md has open tickets ({ids}) but "
              "NEXT_SESSION.md says none are open.")
        failed = failed or args.strict
        warned = True

    # H2 - ROADMAP claims complete while relevant work is uncommitted.
    if re.search(r"\bcomplete\b", _read(ROADMAP), re.IGNORECASE):
        proc = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True)
        untracked = [ln[3:] for ln in proc.stdout.splitlines() if ln.startswith("??")
                     and ln[3:].endswith((".py", ".yaml")) and any(d in ln for d in ("evals/", "tests/", "src/"))]
        if untracked:
            tag = "FAIL" if args.strict else "WARN"
            print(f"check-harness: {tag} [H2] - ROADMAP claims a phase complete, but these are untracked:")
            for f in untracked[:20]:
                print(f"    {f}")
            failed = failed or args.strict
            warned = True

    if not failed and not warned:
        print(f"check-harness: OK - {len(open_blocks)} open ticket(s); debt is tracked, docs consistent.")
    elif not failed:
        print("check-harness: advisory only (warnings above) - not blocking. Use --strict to enforce.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
