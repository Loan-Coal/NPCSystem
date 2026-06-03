#!/usr/bin/env python
"""
Module: check_rules
Layer: harness (repo-level dev tool, outside the package layer model)
Purpose: Enforce the strict CLAUDE.md code rules as an executable, ratcheted gate.
Dependencies: stdlib only.
Used by: `make check-rules`, pre-commit, CI static-analysis.

This scanner turns the prose rules in project-harness/CLAUDE.md into checks. It uses
a *baseline ratchet*: existing (grandfathered) violations are recorded in
scripts/rules_baseline.txt; the gate fails only when a NEW violation appears. Fixing
a baselined violation is reported and can be persisted with --update-baseline, so the
debt can only ever shrink - it can never silently grow.

Rules:
  R001 file-size   - non-test .py over 300 lines (CLAUDE.md "300-line hard limit")
  R002 print       - print() in src/npc_engine (CLAUDE.md "never print(), use logging")
  R003 swallow     - `except ...: pass` (CLAUDE.md "never swallow errors")
  R004 raise-exc   - `raise Exception(` (CLAUDE.md "custom exception hierarchy only")
  R005 cypher-leak - Cypher / session.run / begin_transaction outside graph/ (layer rule)
  R007 demo-import - demo_game importing npc_engine (zero-src-import contract)

Signatures are file-level ("RULE|relative/path") so they stay stable across edits.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "rules_baseline.txt"

MAX_NON_TEST_LINES = 300

# Cypher / transaction patterns that must live in graph/ only.
_CYPHER_RE = re.compile(r"\b(?:MATCH|MERGE|CREATE)\s*\(|session\.run\(|tx\.run\(|begin_transaction\(")
# `except ...: pass` on the same line OR a bare-body `pass` on the next line.
_SWALLOW_RE = re.compile(r"except[^\n:]*:\s*(?:#[^\n]*)?\n\s*pass\b|except[^\n:]*:\s*pass\b")
_RAISE_EXC_RE = re.compile(r"raise\s+Exception\(")
_PRINT_RE = re.compile(r"(?<![\w.])print\(")
_DEMO_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+npc_engine\b", re.MULTILINE)

# Cypher leak is checked in these src/npc_engine subpackages (everything but graph/).
_CYPHER_SCAN_DIRS = ("engines", "world", "retrieval", "services", "scheduler")


def _is_test_path(path: Path) -> bool:
    """True for test files/dirs, which are exempt from size and print rules."""
    parts = {p.lower() for p in path.parts}
    return "tests" in parts or path.name.startswith("test_") or path.name.endswith("_test.py")


def _read(path: Path) -> str:
    """Read a file as UTF-8, ignoring undecodable bytes."""
    return path.read_text(encoding="utf-8", errors="ignore")


def _rel(path: Path) -> str:
    """Repo-relative POSIX path for stable signatures across OSes."""
    return path.relative_to(REPO_ROOT).as_posix()


def _iter_py(root: Path) -> list[Path]:
    """All .py files under a repo subdir (empty list if the dir is absent)."""
    base = REPO_ROOT / root
    return sorted(base.rglob("*.py")) if base.exists() else []


def _collect() -> set[str]:
    """Scan the tree and return the set of current rule-violation signatures."""
    found: set[str] = set()
    src = _iter_py("src/npc_engine")
    demo = _iter_py("demo_game")

    for path in src + demo:
        rel = _rel(path)
        if not _is_test_path(path) and len(_read(path).splitlines()) > MAX_NON_TEST_LINES:
            found.add(f"R001|{rel}")

    for path in src:
        if _is_test_path(path):
            continue
        text = _read(path)
        rel = _rel(path)
        if _PRINT_RE.search(text):
            found.add(f"R002|{rel}")
        if _SWALLOW_RE.search(text):
            found.add(f"R003|{rel}")
        if _RAISE_EXC_RE.search(text):
            found.add(f"R004|{rel}")
        if any(seg in path.parts for seg in _CYPHER_SCAN_DIRS) and _CYPHER_RE.search(text):
            found.add(f"R005|{rel}")

    for path in demo:
        if _DEMO_IMPORT_RE.search(_read(path)):
            found.add(f"R007|{_rel(path)}")
    return found


def _load_baseline() -> set[str]:
    """Load grandfathered signatures from the baseline file (comments allowed)."""
    if not BASELINE_PATH.exists():
        return set()
    lines = _read(BASELINE_PATH).splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def _write_baseline(signatures: set[str]) -> None:
    """Persist the baseline, sorted, with a header."""
    header = (
        "# Grandfathered CLAUDE.md rule violations - see scripts/check_rules.py.\n"
        "# The gate fails only on NEW violations. Shrink this file as debt is fixed\n"
        "# (run `make check-rules-update`). Never add a line by hand to dodge the gate.\n"
    )
    BASELINE_PATH.write_text(header + "\n".join(sorted(signatures)) + "\n", encoding="utf-8")


_RULE_HELP = {
    "R001": "file exceeds 300 non-test lines (split it or add a DECISIONS.md waiver)",
    "R002": "print() in src/ - use utils/logging.py",
    "R003": "swallowed error (`except: pass`) - log-and-(re)raise",
    "R004": "raise Exception(...) - use a typed error from utils/errors.py",
    "R005": "Cypher/transaction outside graph/ - move it into graph/<domain>_queries.py",
    "R007": "demo_game imports npc_engine - use the HTTP client only",
}


def _print_group(title: str, signatures: set[str]) -> None:
    """Print a grouped, rule-annotated list of signatures."""
    print(title)
    for sig in sorted(signatures):
        rule, rel = sig.split("|", 1)
        print(f"  [{rule}] {rel}\n        -> {_RULE_HELP.get(rule, '')}")


def main() -> int:
    """Run the gate. Exit 1 on any new violation; 0 otherwise."""
    parser = argparse.ArgumentParser(description="Enforce CLAUDE.md rules with a baseline ratchet.")
    parser.add_argument("--update-baseline", action="store_true", help="Persist the current set as the baseline.")
    args = parser.parse_args()

    current = _collect()
    if args.update_baseline:
        _write_baseline(current)
        print(f"check-rules: baseline updated - {len(current)} grandfathered violation(s).")
        return 0

    baseline = _load_baseline()
    new = current - baseline
    resolved = baseline - current

    if resolved:
        print(f"check-rules: {len(resolved)} baselined violation(s) resolved - run `make check-rules-update` to ratchet down.")
    if new:
        _print_group(f"\ncheck-rules: FAIL - {len(new)} NEW rule violation(s):", new)
        print("\nFix them, or (only with justification) add a DECISIONS.md entry and re-baseline.")
        return 1
    print(f"check-rules: OK - no new violations ({len(baseline)} grandfathered).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
