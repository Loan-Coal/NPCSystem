"""
Module: test_worktree_guard
Layer: test (unit)
Purpose: Pin that the loop's worktree guard notices a task writing into another worktree.
Dependencies: scripts/worktree_guard.py
Used by: pytest (make test / make check)

Why this exists: on 2026-09-17 the unattended T3.2 session was handed the interactive
session's summary ("Worktree: ...\\NPCSystem, Branch: remediation-2026-08") by a
SessionStart hook, cd'd into the primary checkout and committed there. The loop branch
got the tick without the deletion, and nothing noticed. Pure functions only; no git calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from worktree_guard import changed_worktrees, parse_worktree_heads  # noqa: E402

_PORCELAIN = (
    "worktree C:/repo/NPCSystem\n"
    "HEAD 11275ee8ca4a29d223681af6395383157a060502\n"
    "branch refs/heads/remediation-2026-08\n"
    "\n"
    "worktree C:/repo/NPCSystem-loop\n"
    "HEAD fa9697b0aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
    "branch refs/heads/auto/roadmap-night\n"
)
_MAIN = "C:/repo/NPCSystem"


def test_parse_maps_every_worktree_to_its_head() -> None:
    """Each `worktree` stanza yields its path and HEAD sha."""
    assert parse_worktree_heads(_PORCELAIN) == {
        _MAIN: "11275ee8ca4a29d223681af6395383157a060502",
        "C:/repo/NPCSystem-loop": "fa9697b0aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    }


def test_parse_of_empty_output_is_empty() -> None:
    """No worktrees listed means nothing to guard, not an error."""
    assert parse_worktree_heads("") == {}


def test_unchanged_snapshot_reports_nothing() -> None:
    """Same HEAD and same status fingerprint: the task stayed in its own worktree."""
    snap = {_MAIN: {"head": "57fe6bf4", "status": "e3b0"}}
    assert changed_worktrees(snap, dict(snap)) == []


def test_a_new_commit_in_another_worktree_is_reported() -> None:
    """The 2026-09-17 leak: HEAD of the primary checkout moved during a loop task."""
    before = {_MAIN: {"head": "57fe6bf4", "status": "e3b0"}}
    after = {_MAIN: {"head": "11275ee8", "status": "e3b0"}}
    changes = changed_worktrees(before, after)
    assert len(changes) == 1
    assert _MAIN in changes[0] and "57fe6bf4" in changes[0] and "11275ee8" in changes[0]


def test_uncommitted_edits_in_another_worktree_are_reported() -> None:
    """A leak that edits files without committing changes the status fingerprint."""
    before = {_MAIN: {"head": "57fe6bf4", "status": "e3b0"}}
    after = {_MAIN: {"head": "57fe6bf4", "status": "9f86"}}
    changes = changed_worktrees(before, after)
    assert len(changes) == 1 and "working tree" in changes[0]


def test_a_worktree_that_disappears_is_reported() -> None:
    """A worktree present before the task and gone after it is a change too."""
    before = {_MAIN: {"head": "57fe6bf4", "status": "e3b0"}}
    assert changed_worktrees(before, {}) == [f"{_MAIN}: worktree disappeared"]
