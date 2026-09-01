"""
Module: test_check_cited_reports
Layer: tests (unit)
Purpose: RED anchor + behaviour tests for the cited-report tracking gate (B5/ISSUE-247).
Dependencies: pytest, check_cited_reports (scripts/)
Used by: `make test`, `make check` via test-cov.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_cited_reports import (  # noqa: E402
    REPORT_CITATION,
    cited_reports,
    main,
    untracked,
)

#: The report BASELINE_2026-08-28.md:93 names as the source of record for 0.914 (170/186).
_REPORT_OF_RECORD = "evals/reports/20260825T231028Z.md"


# ---------------------------------------------------------------------------
# cited_reports() — what counts as a citation
# ---------------------------------------------------------------------------


def test_a_bare_path_in_prose_is_a_citation() -> None:
    """The citations this gate exists for are prose references, not code imports."""
    found = cited_reports({"BASELINE.md": f"source of record: `{_REPORT_OF_RECORD}:93`"})

    assert found == {_REPORT_OF_RECORD: ["BASELINE.md"]}


def test_the_same_report_cited_twice_records_both_sites() -> None:
    """The failure message has to name every document that would break."""
    found = cited_reports(
        {"a.md": f"see {_REPORT_OF_RECORD}", "b.md": f"also {_REPORT_OF_RECORD}"}
    )

    assert found[_REPORT_OF_RECORD] == ["a.md", "b.md"]


def test_the_reports_directory_alone_is_not_a_citation() -> None:
    """`evals/reports/` names a location, not an artifact — tracking it is meaningless."""
    assert cited_reports({"a.md": "reports land in evals/reports/ after a run"}) == {}


def test_a_non_report_path_under_evals_is_not_a_citation() -> None:
    """The gate is scoped to reports; generations are already tracked under DEC-158."""
    assert cited_reports({"a.md": "evals/generations/k3_77688e7_regen1/meta.json"}) == {}


def test_the_pattern_accepts_only_the_timestamp_report_name() -> None:
    """A stray `evals/reports/notes.md` is not a run artifact and has no gen to resolve."""
    assert REPORT_CITATION.search("evals/reports/notes.md") is None
    assert REPORT_CITATION.search(f"x {_REPORT_OF_RECORD} y") is not None


# ---------------------------------------------------------------------------
# untracked() — the RED anchor
# ---------------------------------------------------------------------------


def test_an_untracked_cited_report_is_reported(tmp_path: Path) -> None:
    """RED anchor for ISSUE-247.

    `.gitignore` excluded `evals/reports/`, so the artifact publishing 0.914 (170/186) —
    cited as the source of record by BASELINE_2026-08-28.md:93, FINDINGS.md, FIX_PLANS.md
    and TRIAGE.md — existed on one machine and was one `git clean -xdf` from gone. Nothing
    detected that, because nothing ever asked whether a cited file was in the repository.
    """
    assert untracked({"ghost.md": ["doc.md"]}, repo_root=tmp_path) == {"ghost.md": ["doc.md"]}


def test_a_tracked_cited_report_is_not_reported() -> None:
    """The report of record is committed as of B5, so the live repo must be clean."""
    assert untracked({_REPORT_OF_RECORD: ["doc.md"]}, repo_root=REPO_ROOT) == {}


# ---------------------------------------------------------------------------
# The shipped gate against the live tree
# ---------------------------------------------------------------------------


def test_the_report_of_record_is_tracked() -> None:
    """The one citation this gate was written for, asserted directly.

    Kept separate from `main()` so a regression names the specific artifact rather than
    only reporting that some gate went red.
    """
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", _REPORT_OF_RECORD],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"{_REPORT_OF_RECORD} is cited as a source of record but is not tracked; "
        f"the .gitignore negation must use `evals/reports/*`, since git does not "
        f"descend into an excluded directory and a bare `evals/reports/` makes the "
        f"negation inert"
    )


def test_main_is_green_on_the_live_tree() -> None:
    """Every report cited anywhere in project-harness/ must be committed."""
    assert main() == 0
