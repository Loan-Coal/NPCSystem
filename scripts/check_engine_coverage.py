"""
Module: check_engine_coverage
Layer: harness (eval tooling — reads src/npc_engine/engines/ as a directory listing only)
Purpose: EVAL-P25.1 gate. Fail when a unit exists under src/npc_engine/engines/ with no
    classification row in docs/ENGINE_EVAL_COVERAGE.md, when a row names a unit that no
    longer exists, when a unit is classified twice, when a classification is outside the
    closed three-bucket taxonomy, or when a `not_observable` verdict is recorded with no
    reason.
Dependencies: stdlib argparse/pathlib/sys; scripts.engine_coverage_contract.
Used by: `make check-engine-coverage`, tests/unit/scripts/test_check_engine_coverage.py.

Why a gate and not a one-off audit. DEC-214 spent a session remediating A/B arms that
were declared before their supply had been measured. The same rule applied to cases is:
measure observability before authoring. A capability case written against an engine that
never reaches player-visible NPC speech passes unconditionally, which pushes the judged
battery's pass base rate back toward 1.0 — and a base rate at the ceiling is what crushes
kappa (EVAL_P25_TO_P31_PLAN.md §0). An unclassified engine is therefore not a
documentation gap, it is a case-authoring hazard, and it is gated as one.

This module reads only the *names* of the entries under engines/. It imports nothing from
npc_engine, so it stays a harness script and cannot drag the src layer into a gate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from engine_coverage_contract import (  # noqa: E402
    CLASSIFICATION_CELL,
    CLASSIFICATIONS,
    DIALOGUE_OBSERVABLE,
    EVIDENCE_CELL,
    HEADER_UNIT_CELL,
    KIND_CELL,
    MIN_CELLS,
    NO_REASON,
    NOT_OBSERVABLE,
    REASON_CELL,
    SEPARATOR_ROW,
    STATE_OBSERVABLE,
    TABLE_BEGIN,
    TABLE_END,
    UNIT_CELL,
    CoverageReport,
    CoverageRow,
    EngineCoverageDocError,
)

__all__ = [
    "CLASSIFICATIONS",
    "DIALOGUE_OBSERVABLE",
    "DOC_PATH",
    "ENGINES_DIR",
    "NO_REASON",
    "NOT_OBSERVABLE",
    "STATE_OBSERVABLE",
    "TABLE_BEGIN",
    "TABLE_END",
    "CoverageReport",
    "CoverageRow",
    "EngineCoverageDocError",
    "audit",
    "discover_units",
    "load_doc_text",
    "main",
    "parse_rows",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The tree whose entries must all be classified.
ENGINES_DIR: Path = _REPO_ROOT / "src" / "npc_engine" / "engines"

#: The classification table's home.
DOC_PATH: Path = _REPO_ROOT / "docs" / "ENGINE_EVAL_COVERAGE.md"

#: Directory entries that are not units: the package's own marker and build output.
_NOT_A_UNIT: frozenset[str] = frozenset({"__init__.py", "__pycache__"})

_PYTHON_SUFFIX: str = ".py"

_EXIT_OK: int = 0
_EXIT_FAILED: int = 1


# ---------------------------------------------------------------------------
# Discovery and parsing
# ---------------------------------------------------------------------------


def discover_units(engines_dir: Path) -> tuple[str, ...]:
    """Return every unit name under an engines tree, sorted.

    A unit is a subdirectory (a package) or a top-level `.py` file (a module). Both can
    hold engine behaviour, so both need a classification.

    Args:
        engines_dir: Directory to scan.
    Returns:
        Sorted unit names, without the `.py` suffix.
    Raises:
        EngineCoverageDocError: When the directory does not exist.
    """
    if not engines_dir.is_dir():
        raise EngineCoverageDocError(f"engines directory not found: {engines_dir}")
    units: set[str] = set()
    for entry in engines_dir.iterdir():
        if entry.name in _NOT_A_UNIT:
            continue
        if entry.is_dir():
            units.add(entry.name)
        elif entry.suffix == _PYTHON_SUFFIX:
            units.add(entry.stem)
    return tuple(sorted(units))


def _table_body(doc_text: str) -> str:
    """Return the text between the fence markers.

    Raises:
        EngineCoverageDocError: When either marker is absent or they are out of order.
    """
    start = doc_text.find(TABLE_BEGIN)
    end = doc_text.find(TABLE_END)
    if start < 0 or end < 0 or end < start:
        raise EngineCoverageDocError(
            f"coverage doc has no `{TABLE_BEGIN}` ... `{TABLE_END}` fence — "
            "the gate reads the table between those markers and nothing else."
        )
    return doc_text[start + len(TABLE_BEGIN) : end]


def _cells(line: str) -> list[str]:
    """Split one pipe-table line into stripped cells, dropping the outer empties."""
    return [cell.strip().strip("`").strip() for cell in line.strip().strip("|").split("|")]


def parse_rows(doc_text: str) -> tuple[CoverageRow, ...]:
    """Parse the fenced classification table into rows, in document order.

    Header and separator rows are skipped; every other line inside the fence must be a
    pipe row with at least five cells.

    Args:
        doc_text: Full text of the coverage doc.
    Returns:
        The parsed rows.
    Raises:
        EngineCoverageDocError: When the fence is absent or a row is malformed.
    """
    rows: list[CoverageRow] = []
    for line in _table_body(doc_text).splitlines():
        if not line.strip().startswith("|") or SEPARATOR_ROW.match(line):
            continue
        cells = _cells(line)
        if cells[UNIT_CELL].lower() == HEADER_UNIT_CELL:
            continue
        if len(cells) < MIN_CELLS:
            raise EngineCoverageDocError(f"classification row has too few cells: {line!r}")
        rows.append(
            CoverageRow(
                unit=cells[UNIT_CELL],
                kind=cells[KIND_CELL],
                classification=cells[CLASSIFICATION_CELL],
                evidence=cells[EVIDENCE_CELL],
                reason=cells[REASON_CELL],
            )
        )
    return tuple(rows)


def load_doc_text(doc_path: Path = DOC_PATH) -> str:
    """Read the coverage doc, raising rather than returning empty when it is absent."""
    if not doc_path.is_file():
        raise EngineCoverageDocError(f"coverage doc not found: {doc_path}")
    return doc_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def _duplicates(names: tuple[str, ...]) -> tuple[str, ...]:
    """Names appearing more than once, sorted and deduplicated."""
    seen: set[str] = set()
    repeated: set[str] = set()
    for name in names:
        repeated.add(name) if name in seen else seen.add(name)
    return tuple(sorted(repeated))


def audit(engines_dir: Path, doc_text: str) -> CoverageReport:
    """Compare the classification table against the engines tree.

    Args:
        engines_dir: Directory whose units must all be classified.
        doc_text: Full text of the coverage doc.
    Returns:
        A report; `report.ok` is the gate's verdict.
    Raises:
        EngineCoverageDocError: When the tree or the table cannot be read.
    """
    units = discover_units(engines_dir)
    rows = parse_rows(doc_text)
    named = tuple(row.unit for row in rows)
    return CoverageReport(
        units=units,
        rows=rows,
        missing_rows=tuple(sorted(set(units) - set(named))),
        stale_rows=tuple(sorted(set(named) - set(units))),
        duplicate_rows=_duplicates(named),
        bad_classification=tuple(
            sorted({row.unit for row in rows if row.classification not in CLASSIFICATIONS})
        ),
        missing_reason=tuple(
            sorted(
                {
                    row.unit
                    for row in rows
                    if row.classification == NOT_OBSERVABLE and not row.has_reason
                }
            )
        ),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Build the CLI parser and parse `argv`."""
    parser = argparse.ArgumentParser(
        description="Fail when an engine unit has no row in docs/ENGINE_EVAL_COVERAGE.md."
    )
    parser.add_argument("--engines-dir", type=Path, default=ENGINES_DIR)
    parser.add_argument("--doc", type=Path, default=DOC_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the gate and print the split or the failures.

    Args:
        argv: Command-line arguments; None reads `sys.argv`.
    Returns:
        0 when every unit is classified exactly once and legally, 1 otherwise.
    """
    args = _parse_args(argv)
    report = audit(args.engines_dir, load_doc_text(args.doc))
    counts = report.counts_by_classification()
    print(f"engine units: {len(report.units)}   rows: {len(report.rows)}")
    for name in sorted(counts):
        print(f"  {name:<20} {counts[name]}")
    if report.ok:
        return _EXIT_OK
    print("\nFAIL — docs/ENGINE_EVAL_COVERAGE.md and src/npc_engine/engines/ disagree:")
    print(report.failure_report())
    return _EXIT_FAILED


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
