#!/usr/bin/env python
"""
Module: worktree_guard
Layer: harness (repo-level dev tool)
Purpose: Detect an overnight-loop task that wrote into a git worktree other than its own.
Dependencies: stdlib + git on PATH.
Used by: scripts/expand_loop.sh (run_one_task), around every `claude -p` task session.

On 2026-09-17 the unattended T3.2 session was fed the interactive session's summary by a
SessionStart hook, cd'd into the primary checkout and committed there; the loop branch got the
roadmap tick without the change. `snapshot` records HEAD and a working-tree fingerprint for
every OTHER worktree before a task; `check` exits 1 naming each one that changed after it.

Usage:
    python scripts/worktree_guard.py snapshot > before.json
    python scripts/worktree_guard.py check before.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

_WORKTREE_PREFIX = "worktree "
_HEAD_PREFIX = "HEAD "
_MISSING = "<missing>"

Snapshot = dict[str, dict[str, str]]


def parse_worktree_heads(porcelain: str) -> dict[str, str]:
    """Map each worktree path in `git worktree list --porcelain` output to its HEAD sha.

    Args:
        porcelain: Raw stdout of `git worktree list --porcelain`.

    Returns:
        Worktree path -> HEAD sha, in listing order.
    """
    heads: dict[str, str] = {}
    path: str | None = None
    for line in porcelain.splitlines():
        if line.startswith(_WORKTREE_PREFIX):
            path = line[len(_WORKTREE_PREFIX):]
        elif line.startswith(_HEAD_PREFIX) and path is not None:
            heads[path] = line[len(_HEAD_PREFIX):]
    return heads


def changed_worktrees(before: Snapshot, after: Snapshot) -> list[str]:
    """Describe every worktree whose HEAD or working tree differs between two snapshots.

    Args:
        before: Snapshot taken before the task.
        after: Snapshot taken after the task.

    Returns:
        One human-readable line per changed worktree; empty when nothing changed.
    """
    changes: list[str] = []
    for path, old in before.items():
        new = after.get(path)
        if new is None:
            changes.append(f"{path}: worktree disappeared")
        elif new["head"] != old["head"]:
            changes.append(f"{path}: HEAD moved {old['head']} -> {new['head']}")
        elif new["status"] != old["status"]:
            changes.append(f"{path}: working tree changed (git status differs)")
    return changes


def _git(args: list[str], cwd: str) -> str:
    """Run git in `cwd` and return stdout; raise CalledProcessError on failure."""
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def take_snapshot(own_root: Path) -> Snapshot:
    """Record HEAD and a `git status` fingerprint for every worktree except `own_root`.

    Args:
        own_root: Top level of the worktree the loop runs in (excluded from the snapshot).

    Returns:
        Worktree path -> {"head": sha, "status": sha256 of `git status --porcelain`}.
    """
    snapshot: Snapshot = {}
    heads = parse_worktree_heads(_git(["worktree", "list", "--porcelain"], str(own_root)))
    for path, head in heads.items():
        if Path(path).resolve() == own_root.resolve():
            continue
        try:
            status = _git(["status", "--porcelain"], path)
        except (subprocess.CalledProcessError, OSError):
            status = _MISSING
        snapshot[path] = {"head": head, "status": hashlib.sha256(status.encode()).hexdigest()}
    return snapshot


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: `snapshot` prints JSON; `check <file>` exits 1 on any change."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot")
    check = sub.add_parser("check")
    check.add_argument("before", type=Path)
    args = parser.parse_args(argv)

    own_root = Path(_git(["rev-parse", "--show-toplevel"], ".").strip())
    if args.cmd == "snapshot":
        print(json.dumps(take_snapshot(own_root), sort_keys=True))
        return 0
    before: Snapshot = json.loads(args.before.read_text(encoding="utf-8"))
    changes = changed_worktrees(before, take_snapshot(own_root))
    for line in changes:
        print(line)
    return 1 if changes else 0


if __name__ == "__main__":
    sys.exit(main())
