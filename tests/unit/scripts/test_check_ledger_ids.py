"""
Module: test_check_ledger_ids
Layer: tests (unit)
Purpose: RED anchor + behaviour tests for the ledger id-collision detector (R4.5).
Dependencies: pytest, check_ledger_ids (scripts/)
Used by: `make test`, `make check` via test-cov.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_ledger_ids import (  # noqa: E402
    collisions,
    declarations,
    documented_reuses,
    main,
    unresolved_citations,
)


# ---------------------------------------------------------------------------
# declarations() — what counts as declaring an id
# ---------------------------------------------------------------------------


def test_a_declaration_heading_is_counted() -> None:
    text = "## DEC-051: S10.3 correct rumor marks 'corrected'\nbody\n"
    assert declarations(text, "DEC") == {"DEC-051": [1]}


def test_a_fixed_prefix_still_declares() -> None:
    text = "## [FIXED] ISSUE-035: tone_judge matcher is stubbed\n"
    assert declarations(text, "ISSUE") == {"ISSUE-035": [1]}


def test_an_outcome_continuation_heading_is_not_a_declaration() -> None:
    """DEC-116 is one decision under a question heading plus an outcome heading."""
    text = (
        "## DEC-116: Is the summary template prompt content?\n"
        "## DEC-116 outcome (2026-06-14): NOT LLM-bound — kept in Python\n"
    )
    assert declarations(text, "DEC") == {"DEC-116": [1]}
    assert collisions({"a": text}, "DEC") == {}


def test_body_prose_mentioning_an_id_is_not_a_declaration() -> None:
    text = "## DEC-051: a title\nSee DEC-052 and DEC-058 for context.\n"
    assert declarations(text, "DEC") == {"DEC-051": [1]}


# ---------------------------------------------------------------------------
# collisions()
# ---------------------------------------------------------------------------


def test_two_declarations_of_one_id_collide() -> None:
    text = "## DEC-051: first meaning\n## DEC-051: second meaning\n"
    assert collisions({"DECISIONS.md": text}, "DEC") == {"DEC-051": ["DECISIONS.md:1", "DECISIONS.md:2"]}


def test_collisions_span_multiple_files() -> None:
    found = collisions(
        {"ISSUES.md": "## ISSUE-056: open one\n", "archive.md": "## [FIXED] ISSUE-056: fixed one\n"},
        "ISSUE",
    )
    assert set(found) == {"ISSUE-056"}


# ---------------------------------------------------------------------------
# documented_reuses() — the disambiguation note
# ---------------------------------------------------------------------------


def test_a_note_entry_documents_its_id() -> None:
    note = "## Reused ids\n- `DEC-051` — two meanings: rumor correction; run_scenes line waiver.\n"
    assert documented_reuses(note) == {"DEC-051"}


def test_an_empty_note_documents_nothing() -> None:
    assert documented_reuses("no note here\n") == set()


# ---------------------------------------------------------------------------
# main() — the gate contract
# ---------------------------------------------------------------------------


def test_an_undocumented_collision_reds(tmp_path: Path) -> None:
    dec = tmp_path / "DECISIONS.md"
    dec.write_text("## DEC-051: first\n## DEC-051: second\n", encoding="utf-8")
    (tmp_path / "ISSUES.md").write_text("", encoding="utf-8")
    (tmp_path / "archive").mkdir(exist_ok=True)
    (tmp_path / "archive" / "ISSUES_RESOLVED.md").write_text("", encoding="utf-8")
    assert main(root=tmp_path) == 1


def test_a_documented_collision_greens(tmp_path: Path) -> None:
    dec = tmp_path / "DECISIONS.md"
    dec.write_text(
        "## Reused ids\n- `DEC-051` — two meanings, both retained.\n"
        "## DEC-051: first\n## DEC-051: second\n",
        encoding="utf-8",
    )
    (tmp_path / "ISSUES.md").write_text("", encoding="utf-8")
    (tmp_path / "archive").mkdir(exist_ok=True)
    (tmp_path / "archive" / "ISSUES_RESOLVED.md").write_text("", encoding="utf-8")
    assert main(root=tmp_path) == 0


# ---------------------------------------------------------------------------
# unresolved_citations() — ids cited by a document but never declared
# ---------------------------------------------------------------------------


def test_a_citation_to_an_undeclared_id_is_unresolved() -> None:
    found = unresolved_citations(
        citing={"ROADMAP.md": "see ISSUE-242 for the counts\n"},
        declared={"ISSUE-233"},
        prefix="ISSUE",
    )
    assert found == {"ISSUE-242": ["ROADMAP.md:1"]}


def test_a_citation_to_a_declared_id_resolves() -> None:
    found = unresolved_citations(
        citing={"ROADMAP.md": "see ISSUE-233\n"}, declared={"ISSUE-233"}, prefix="ISSUE"
    )
    assert found == {}


# ---------------------------------------------------------------------------
# RED anchor — the live ledgers
# ---------------------------------------------------------------------------


def test_the_live_ledgers_document_every_reused_id() -> None:
    """RED until the disambiguation notes land; 6 collisions measured 2026-09-01."""
    assert main(root=REPO_ROOT / "project-harness") == 0
