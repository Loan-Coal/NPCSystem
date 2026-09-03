#!/usr/bin/env python
"""
Module: check_readme_paths
Layer: scripts (dev tooling)
Purpose: Fail when README.md links to a path that does not exist, so the "Key files"
         table cannot go on pointing at a source layout the repo abandoned (R4.6).
Does NOT: follow external URLs, or check anchors within a file.
Dependencies: pathlib, re, sys
Dependencies injected: None.
Used by: make check-readme-paths, tests/unit/scripts/test_check_readme_paths.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def repo_relative_links(text: str) -> list[str]:
    """Return every markdown link target that names a path inside the repo.

    External URLs, mailto targets and pure `#anchor` links are excluded, since
    none of them is a path this gate can resolve.

    Args:
        text: Markdown source.

    Returns:
        Link targets, anchors stripped, in document order.
    """
    targets: list[str] = []
    for raw in LINK_PATTERN.findall(text):
        target = raw.split("#", 1)[0].strip()
        if not target or "://" in target or target.startswith(("mailto:", "#")):
            continue
        targets.append(target)
    return targets


def missing_paths(doc: Path = REPO_ROOT / "README.md") -> list[str]:
    """Return the link targets in `doc` that do not resolve to a file or directory."""
    text = doc.read_text(encoding="utf-8")
    return [t for t in repo_relative_links(text) if not (doc.parent / t).exists()]


def main(argv: Sequence[str] | None = None) -> int:
    """Report unresolvable README links.

    Args:
        argv: Optional list of markdown files; defaults to README.md.

    Returns:
        1 when any link does not resolve, else 0.
    """
    docs = [Path(a) for a in (argv or [])] or [REPO_ROOT / "README.md"]
    bad: list[str] = []
    for doc in docs:
        for target in missing_paths(doc):
            bad.append(f"{doc.name}: {target}")
    print("check-readme-paths:")
    for row in bad:
        print(f"  MISSING {row}")
    if bad:
        print(f"  FAIL - {len(bad)} link(s) point at nothing.")
        return 1
    print("  OK - every repo-relative link resolves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
