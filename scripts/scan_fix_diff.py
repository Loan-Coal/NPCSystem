"""
Module: scan_fix_diff
Layer: harness
Purpose: Scan a repair session's diff for gate-gaming — changes that make a red gate
    green without fixing anything — before that repair is allowed to be committed.
Dependencies: scripts/loop_gates (frozen paths + suppression patterns), stdlib.
Used by: scripts/expand_loop.sh (after every /fix-make-failure session).

Two independent detections:

1. **Frozen paths.** A repair must not touch tests, the gate scripts, CI, or the
   Makefile. The one specific to this repo is `scripts/rules_baseline.txt`: the project
   ships `make check-rules-update`, which legitimately rewrites the violation baseline,
   so a repair session that runs it launders every new violation into "expected" and the
   gate goes green having fixed nothing.
2. **Suppression patterns.** Added lines that silence a check (`# noqa`, `# type:
   ignore`, `except: pass`, `@pytest.mark.skip`, lowering `--cov-fail-under`) rather
   than satisfy it.

Exit codes:
    0  clean — the repair may be committed
    1  gaming detected — revert the repair, do not commit
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop_gates import (  # noqa: E402
    FROZEN_PATH_PREFIXES,
    REPO_ROOT,
    SUPPRESSION_PATTERNS,
)

DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
ADDED_LINE_RE = re.compile(r"^\+(?!\+\+ )(.*)$")
EXIT_CLEAN = 0
EXIT_GAMING = 1


@dataclass(frozen=True)
class Finding:
    """One gaming detection: which rule fired, in which file, on what evidence."""

    rule: str
    path: str
    evidence: str

    def render(self) -> str:
        """One-line report form."""
        return f"GAMING [{self.rule}] {self.path}: {self.evidence.strip()[:120]}"


def read_diff(rev_range: str | None) -> str:
    """Return the unified diff to scan — from a git range, or the working tree."""
    argv = ["git", "diff", "--unified=0"]
    if rev_range:
        argv.append(rev_range)
    completed = subprocess.run(
        argv, cwd=str(REPO_ROOT), capture_output=True, check=False
    )
    return completed.stdout.decode("utf-8", errors="replace")


def scan(diff_text: str) -> list[Finding]:
    """Walk a unified diff and collect every frozen-path and suppression finding.

    Args:
        diff_text: Unified diff output.
    Returns:
        Findings in file order; empty means the diff is clean.
    """
    findings: list[Finding] = []
    current = "<unknown>"
    compiled = [(rule, re.compile(pattern)) for rule, pattern in SUPPRESSION_PATTERNS]
    for line in diff_text.splitlines():
        file_match = DIFF_FILE_RE.match(line)
        if file_match:
            current = file_match.group(1).replace("\\", "/")
            if current.startswith(FROZEN_PATH_PREFIXES):
                findings.append(
                    Finding(rule="frozen-path", path=current, evidence="file was modified")
                )
            continue
        added = ADDED_LINE_RE.match(line)
        if not added:
            continue
        for rule, pattern in compiled:
            if pattern.search(added.group(1)):
                findings.append(Finding(rule=rule, path=current, evidence=added.group(1)))
    return findings


def main(argv: list[str] | None = None) -> int:
    """Scan a diff and report findings; non-zero means the repair must be reverted."""
    parser = argparse.ArgumentParser(description="Scan a repair diff for gate-gaming.")
    parser.add_argument("--range", dest="rev_range", default=None, help="git rev range")
    parser.add_argument("--stdin", action="store_true", help="read the diff from stdin")
    args = parser.parse_args(argv)

    diff_text = sys.stdin.read() if args.stdin else read_diff(args.rev_range)
    findings = scan(diff_text)
    for finding in findings:
        print(finding.render())
    if findings:
        print(f"SCAN=GAMING COUNT={len(findings)}")
        return EXIT_GAMING
    print("SCAN=CLEAN")
    return EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
