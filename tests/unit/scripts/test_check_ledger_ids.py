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
    _DECISION_FILES,
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


# ---------------------------------------------------------------------------
# RED anchor — DECISIONS_history declared before T22.3 creates it (DEC-327)
# ---------------------------------------------------------------------------


def test_decisions_history_is_in_decision_files() -> None:
    """check_ledger_ids must declare archive/DECISIONS_history.md before T22.3 creates it.

    DEC-327: the history file is cited in ROADMAP.md (T22.3) before it exists; declaring
    it in _DECISION_FILES prevents check-ledger-ids from treating those forward citations
    as undeclared references.
    """
    assert "archive/DECISIONS_history.md" in _DECISION_FILES


# ---------------------------------------------------------------------------
# cited_reports() — merged from check_cited_reports.py (T22.2)
# ---------------------------------------------------------------------------

_REPORT_OF_RECORD = "evals/reports/20260825T231028Z.md"


def test_a_bare_path_in_prose_is_a_citation() -> None:
    """The citations this gate exists for are prose references, not code imports."""
    from check_ledger_ids import cited_reports  # noqa: PLC0415

    found = cited_reports({"BASELINE.md": f"source of record: `{_REPORT_OF_RECORD}:93`"})

    assert found == {_REPORT_OF_RECORD: ["BASELINE.md"]}


def test_the_same_report_cited_twice_records_both_sites() -> None:
    """The failure message has to name every document that would break."""
    from check_ledger_ids import cited_reports  # noqa: PLC0415

    found = cited_reports(
        {"a.md": f"see {_REPORT_OF_RECORD}", "b.md": f"also {_REPORT_OF_RECORD}"}
    )

    assert found[_REPORT_OF_RECORD] == ["a.md", "b.md"]


def test_the_reports_directory_alone_is_not_a_citation() -> None:
    """`evals/reports/` names a location, not an artifact — tracking it is meaningless."""
    from check_ledger_ids import cited_reports  # noqa: PLC0415

    assert cited_reports({"a.md": "reports land in evals/reports/ after a run"}) == {}


def test_a_non_report_path_under_evals_is_not_a_citation() -> None:
    """The gate is scoped to reports; generations are already tracked under DEC-158."""
    from check_ledger_ids import cited_reports  # noqa: PLC0415

    assert cited_reports({"a.md": "evals/generations/k3_77688e7_regen1/meta.json"}) == {}


def test_the_pattern_accepts_only_the_timestamp_report_name() -> None:
    """A stray `evals/reports/notes.md` is not a run artifact and has no gen to resolve."""
    from check_ledger_ids import REPORT_CITATION  # noqa: PLC0415

    assert REPORT_CITATION.search("evals/reports/notes.md") is None
    assert REPORT_CITATION.search(f"x {_REPORT_OF_RECORD} y") is not None


def test_an_untracked_cited_report_is_reported(tmp_path: Path) -> None:
    """RED anchor for ISSUE-247: a cited report that exists only on one machine."""
    from check_ledger_ids import untracked_cited_reports  # noqa: PLC0415

    assert untracked_cited_reports({"ghost.md": ["doc.md"]}, repo_root=tmp_path) == {
        "ghost.md": ["doc.md"]
    }


def test_a_tracked_cited_report_is_not_reported() -> None:
    """The report of record is committed as of B5, so the live repo must be clean."""
    from check_ledger_ids import untracked_cited_reports  # noqa: PLC0415

    assert untracked_cited_reports({_REPORT_OF_RECORD: ["doc.md"]}, repo_root=REPO_ROOT) == {}


def test_the_report_of_record_is_tracked() -> None:
    """The one citation this gate was written for, asserted directly (ISSUE-247)."""
    import subprocess  # noqa: PLC0415

    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", _REPORT_OF_RECORD],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"{_REPORT_OF_RECORD} is cited as a source of record but is not tracked; "
        f"the .gitignore negation must use `evals/reports/*`, not `evals/reports/`"
    )
