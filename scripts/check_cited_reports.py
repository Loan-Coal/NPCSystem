#!/usr/bin/env python
"""
Module: check_cited_reports
Layer: harness (repo-level dev tool)
Purpose: Red when a document cites an eval report that is not tracked by git, so a number
         published from a machine-local artifact cannot survive review (B5/ISSUE-247).
Dependencies: stdlib only.
Used by: `make check-cited-reports`, and tests/unit/scripts/test_check_cited_reports.py.

Why "tracked when cited" rather than "all reports tracked" (DEC-241): `evals/reports/`
holds 421 files totalling 4.7 MB, of which roughly 396 are near-identical 824-924 byte
run stubs, and exactly ONE is cited as a source of record anywhere in project-harness/.
Committing all of them would bury the one artifact that matters in noise and dirty the
working tree after every eval run. Committing only what is cited fixes the actual harm --
a published number resting on a file that exists on one machine -- and scales, because a
future citation reds this gate until the report it names is committed too.

Why the `.gitignore` form matters: git does not descend into an excluded directory, so
`evals/reports/` followed by `!evals/reports/keep.md` leaves the file ignored and the
negation inert. The ignore must be written `evals/reports/*` for the negation to bind.
That is the trap this gate would otherwise have to catch a second time.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_ROOT = REPO_ROOT / "project-harness"

#: Documents scanned for citations. Reports are quoted in prose, never imported by code.
_CITING_GLOB = "**/*.md"

#: A run report is `evals/reports/<UTC timestamp>.md`. Restricting the pattern to the
#: timestamp shape keeps `evals/reports/` (a location, not an artifact) from matching, and
#: keeps a hand-written note dropped in the directory from being demanded as a citation.
REPORT_CITATION: re.Pattern[str] = re.compile(r"evals/reports/\d{8}T\d{6}Z\.md")


def cited_reports(texts: dict[str, str]) -> dict[str, list[str]]:
    """Map each cited report path to the documents citing it.

    Args:
        texts: document name -> full text.
    Returns:
        report path -> sorted citing document names. Empty when nothing is cited.
    """
    found: dict[str, list[str]] = defaultdict(list)
    for name in sorted(texts):
        for report in sorted(set(REPORT_CITATION.findall(texts[name]))):
            found[report].append(name)
    return dict(found)


def _is_tracked(path: str, repo_root: Path) -> bool:
    """True when git has `path` in the index."""
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def untracked(citations: dict[str, list[str]], repo_root: Path = REPO_ROOT) -> dict[str, list[str]]:
    """Filter `citations` down to the reports git does not track.

    Args:
        citations: report path -> citing document names, as `cited_reports` returns.
        repo_root: Repository to resolve the paths against.
    Returns:
        The same mapping, restricted to reports that are not in the index.
    """
    return {r: sites for r, sites in citations.items() if not _is_tracked(r, repo_root)}


def _read_docs(root: Path) -> dict[str, str]:
    """Every markdown document under `root`, keyed by its path relative to the repo."""
    return {
        path.relative_to(REPO_ROOT).as_posix(): path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(root.glob(_CITING_GLOB))
        if path.is_file()
    }


def main(root: Path | None = None) -> int:
    """Red when any cited eval report is untracked.

    Args:
        root: Directory of citing documents; defaults to project-harness/.
    Returns:
        0 when every cited report is committed, else 1.
    """
    base = HARNESS_ROOT if root is None else root
    citations = cited_reports(_read_docs(base))
    missing = untracked(citations)

    print("check-cited-reports:")
    for report, sites in sorted(missing.items()):
        print(f"  UNTRACKED {report} cited at {', '.join(sites)}")

    if missing:
        print(
            f"  FAIL - {len(missing)} cited report(s) are not committed. A number whose "
            f"source of record exists on one machine is not reproducible (ISSUE-247). "
            f"Commit them, and check that .gitignore excludes `evals/reports/*` rather "
            f"than `evals/reports/`, or the negation will not bind."
        )
        return 1
    print(f"  OK - all {len(citations)} cited report(s) are tracked.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cited eval-report tracking gate (B5).")
    parser.add_argument("--root", type=Path, default=None, help="Directory of citing docs.")
    sys.exit(main(root=parser.parse_args().root))
