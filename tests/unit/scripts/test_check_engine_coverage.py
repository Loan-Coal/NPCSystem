"""
Module: test_check_engine_coverage
Layer: test (unit)
Purpose: Unit tests for scripts/check_engine_coverage.py — the EVAL-P25.1 gate that
         refuses to let a package exist under src/npc_engine/engines/ without a
         classification row in docs/ENGINE_EVAL_COVERAGE.md. The RED anchor is
         `test_a_package_with_no_row_fails_the_gate`: a fixture package with no row
         must fail BEFORE its row is added, or the gate proves nothing.
Dependencies: pathlib, sys, pytest, check_engine_coverage (scripts/)
Used by: pytest (make test / make check)

Why this gate exists at all. DEC-214 spent a session remediating A/B arms declared
before their supply was measured. A capability case authored against an engine that
never reaches player-visible NPC speech passes unconditionally, which drags the judged
battery's pass base rate back toward 1.0 — the exact defect EVAL-P25 exists to fix.
Classifying observability is measuring supply before authoring.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_engine_coverage import (  # noqa: E402
    CLASSIFICATIONS,
    DIALOGUE_OBSERVABLE,
    ENGINES_DIR,
    NO_REASON,
    NOT_OBSERVABLE,
    STATE_OBSERVABLE,
    TABLE_BEGIN,
    TABLE_END,
    EngineCoverageDocError,
    audit,
    discover_units,
    load_doc_text,
    main,
    parse_rows,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_HEADER = (
    "| Unit | Kind | Classification | Evidence | Why not observable |\n"
    "| --- | --- | --- | --- | --- |"
)


def _doc(*rows: str) -> str:
    """Wrap table rows in the marker fence the parser looks for."""
    body = "\n".join([_HEADER, *rows])
    return f"# Fixture\n\nprose\n\n{TABLE_BEGIN}\n{body}\n{TABLE_END}\n\nmore prose\n"


def _row(unit: str, classification: str = STATE_OBSERVABLE, reason: str = NO_REASON) -> str:
    """One pipe-table row in the shipped column order."""
    return f"| `{unit}` | package | `{classification}` | writes graph state | {reason} |"


def _engines_dir(
    tmp_path: Path, packages: tuple[str, ...], modules: tuple[str, ...] = ()
) -> Path:
    """Build a throwaway engines/ tree with the named packages and top-level modules."""
    root = tmp_path / "engines"
    root.mkdir()
    (root / "__init__.py").write_text('"""package init."""\n', encoding="utf-8")
    (root / "__pycache__").mkdir()
    for name in packages:
        pkg = root / name
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""fixture package."""\n', encoding="utf-8")
    for name in modules:
        (root / f"{name}.py").write_text('"""fixture module."""\n', encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_a_package_with_no_row_fails_the_gate(tmp_path: Path) -> None:
    """THE RED ANCHOR. An unclassified package is a hole, and the gate must say so.

    Before `beta`'s row exists the audit reports it missing and is not ok; adding the
    row — and nothing else — turns it green. If this passes in both directions the
    gate is load-bearing; if it passes in the first, it is decoration.
    """
    engines = _engines_dir(tmp_path, ("alpha", "beta"))

    before = audit(engines, _doc(_row("alpha")))
    assert not before.ok
    assert before.missing_rows == ("beta",)

    after = audit(engines, _doc(_row("alpha"), _row("beta")))
    assert after.ok, after.failure_report()
    assert after.missing_rows == ()


# ---------------------------------------------------------------------------
# Unit discovery
# ---------------------------------------------------------------------------


def test_discover_units_finds_packages_and_top_level_modules(tmp_path: Path) -> None:
    """Both a directory package and a bare .py module are units needing a row."""
    engines = _engines_dir(tmp_path, ("gossip", "emotion"), ("base_engine", "embedding_refresh"))
    assert discover_units(engines) == ("base_engine", "embedding_refresh", "emotion", "gossip")


def test_discover_units_excludes_package_init_and_pycache(tmp_path: Path) -> None:
    """`__init__.py` is the package's own marker and `__pycache__` is build output."""
    units = discover_units(_engines_dir(tmp_path, ("gossip",)))
    assert "__init__" not in units
    assert "__pycache__" not in units


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------


def test_parse_rows_reads_backticked_cells() -> None:
    """Unit and classification cells are written in backticks in the shipped doc."""
    rows = parse_rows(_doc(_row("gossip", DIALOGUE_OBSERVABLE)))
    assert len(rows) == 1
    assert rows[0].unit == "gossip"
    assert rows[0].classification == DIALOGUE_OBSERVABLE


def test_parse_rows_ignores_tables_outside_the_marker_fence() -> None:
    """Prose tables elsewhere in the doc must not be mistaken for classification rows."""
    text = _doc(_row("gossip")) + "\n| Unit | Kind |\n| --- | --- |\n| decoy | package |\n"
    assert [row.unit for row in parse_rows(text)] == ["gossip"]


def test_parse_rows_raises_when_the_fence_is_absent() -> None:
    """A doc with no table fence is a doc the gate cannot read — fail loudly, not empty."""
    with pytest.raises(EngineCoverageDocError):
        parse_rows("# no table here\n")


# ---------------------------------------------------------------------------
# The four failure modes
# ---------------------------------------------------------------------------


def test_a_row_naming_a_unit_that_does_not_exist_is_stale(tmp_path: Path) -> None:
    """A deleted engine must not leave a row behind claiming coverage of nothing."""
    report = audit(_engines_dir(tmp_path, ("alpha",)), _doc(_row("alpha"), _row("ghost")))
    assert not report.ok
    assert report.stale_rows == ("ghost",)


def test_two_rows_for_one_unit_are_a_duplicate(tmp_path: Path) -> None:
    """Exactly one classification per unit — two rows can disagree, and one must win."""
    report = audit(_engines_dir(tmp_path, ("alpha",)), _doc(_row("alpha"), _row("alpha")))
    assert not report.ok
    assert report.duplicate_rows == ("alpha",)


def test_a_classification_outside_the_three_is_rejected(tmp_path: Path) -> None:
    """The taxonomy is closed: three buckets, no `partially`, no `tbd`."""
    report = audit(_engines_dir(tmp_path, ("alpha",)), _doc(_row("alpha", "maybe_observable")))
    assert not report.ok
    assert report.bad_classification == ("alpha",)


def test_not_observable_without_a_reason_is_rejected(tmp_path: Path) -> None:
    """`not_observable` is the bucket that excuses an engine from measurement.

    An excuse with no reason recorded is how a judgeable engine quietly disappears, so
    the reason cell is mandatory for exactly this class and optional for the others.
    """
    engines = _engines_dir(tmp_path, ("alpha",))

    report = audit(engines, _doc(_row("alpha", NOT_OBSERVABLE)))
    assert not report.ok
    assert report.missing_reason == ("alpha",)

    with_reason = audit(
        engines,
        _doc(_row("alpha", NOT_OBSERVABLE, "transport plumbing, no NPC speech")),
    )
    assert with_reason.ok, with_reason.failure_report()


def test_the_three_classifications_are_the_whole_taxonomy() -> None:
    """Pin the closed set so a fourth bucket cannot be added without a test edit."""
    assert CLASSIFICATIONS == frozenset({DIALOGUE_OBSERVABLE, STATE_OBSERVABLE, NOT_OBSERVABLE})


# ---------------------------------------------------------------------------
# The shipped doc against the shipped engines
# ---------------------------------------------------------------------------


def test_the_shipped_doc_classifies_every_shipped_engine() -> None:
    """The real gate: docs/ENGINE_EVAL_COVERAGE.md against src/npc_engine/engines/."""
    report = audit(ENGINES_DIR, load_doc_text())
    assert report.ok, report.failure_report()


def test_the_shipped_doc_finds_at_least_one_dialogue_observable_engine() -> None:
    """A table where nothing is judgeable would make the whole capability battery void."""
    rows = parse_rows(load_doc_text())
    observable = [row.unit for row in rows if row.classification == DIALOGUE_OBSERVABLE]
    assert "dialogue" in observable
    assert len(observable) >= 2


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_main_exits_zero_on_the_shipped_tree() -> None:
    """`make check-engine-coverage` must be green on the tree it ships with."""
    assert main([]) == 0


def test_main_exits_one_when_a_unit_is_unclassified(tmp_path: Path) -> None:
    """The gate's exit code is what wires it into make; it must be non-zero when red."""
    engines = _engines_dir(tmp_path, ("alpha", "beta"))
    doc = tmp_path / "COVERAGE.md"
    doc.write_text(_doc(_row("alpha")), encoding="utf-8")
    assert main(["--engines-dir", str(engines), "--doc", str(doc)]) == 1
