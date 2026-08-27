"""
Module: engine_coverage_contract
Layer: harness (eval tooling — imports nothing from npc_engine)
Purpose: The vocabulary of the EVAL-P25.1 engine-observability audit — the closed
    classification taxonomy, the table's fence markers and cell layout, and the two
    Pydantic v2 models the gate reports through (`CoverageRow`, `CoverageReport`).
Dependencies: stdlib re; pydantic v2.
Used by: scripts/check_engine_coverage.py, tests/unit/scripts/test_check_engine_coverage.py.

Split out of `check_engine_coverage.py` to hold that module under CLAUDE.md's 300-line
cap, in the same shape as `base_rate_contract.py` / `check_base_rate.py`: this file is the
data model and the constants, and the gate module is the discovery, parsing and CLI.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# The table's fence and cell layout
# ---------------------------------------------------------------------------

#: Fence markers around the machine-read table. Everything outside them is prose the
#: parser must ignore, so the doc can carry other tables without confusing the gate.
TABLE_BEGIN: str = "<!-- ENGINE-COVERAGE-TABLE: BEGIN -->"
TABLE_END: str = "<!-- ENGINE-COVERAGE-TABLE: END -->"

MIN_CELLS: int = 5
UNIT_CELL: int = 0
KIND_CELL: int = 1
CLASSIFICATION_CELL: int = 2
EVIDENCE_CELL: int = 3
REASON_CELL: int = 4

SEPARATOR_ROW: re.Pattern[str] = re.compile(r"^[\s|:-]+$")
HEADER_UNIT_CELL: str = "unit"

# ---------------------------------------------------------------------------
# The closed taxonomy
# ---------------------------------------------------------------------------

#: Reaches player-visible NPC speech, so an LLM judge or a keyword matcher can measure it.
DIALOGUE_OBSERVABLE: str = "dialogue_observable"

#: Verifiable only through the graph — belongs in a deterministic or scenario check.
STATE_OBSERVABLE: str = "state_observable"

#: Infrastructure. Out of scope for the judged battery, and the row must say why.
NOT_OBSERVABLE: str = "not_observable"

#: The closed taxonomy. A fourth bucket is a decision, not an edit.
CLASSIFICATIONS: frozenset[str] = frozenset(
    {DIALOGUE_OBSERVABLE, STATE_OBSERVABLE, NOT_OBSERVABLE}
)

#: The placeholder written in the reason column when no reason is required.
NO_REASON: str = "—"


class EngineCoverageDocError(ValueError):
    """Raised when the coverage doc or the engines tree cannot be read.

    An unreadable table must not degrade to "zero rows found", because zero rows and a
    fully classified tree are opposite results that would otherwise look identical to a
    caller that only checked `missing_rows`.
    """


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CoverageRow(BaseModel):
    """One classification row: a unit under engines/ and what it is observable through.

    Attributes:
        unit: Package directory name or top-level module stem, without `.py`.
        kind: `package` or `module` — how the unit is spelled on disk.
        classification: One of `CLASSIFICATIONS`.
        evidence: What was checked to reach the verdict (a slot, a port, a prompt rule).
        reason: Why the unit is out of scope. Mandatory when `not_observable`.
    """

    model_config = ConfigDict(frozen=True)

    unit: str
    kind: str
    classification: str
    evidence: str
    reason: str

    @property
    def has_reason(self) -> bool:
        """True when the reason cell carries text rather than the `—` placeholder."""
        return bool(self.reason) and self.reason != NO_REASON


class CoverageReport(BaseModel):
    """The five ways the table and the tree can disagree.

    Attributes:
        units: Every unit discovered under the engines tree, sorted.
        rows: Every classification row parsed from the doc, in document order.
        missing_rows: Units with no row — the gate's headline failure.
        stale_rows: Rows naming a unit that is not on disk.
        duplicate_rows: Units classified more than once.
        bad_classification: Rows whose classification is outside the closed taxonomy.
        missing_reason: `not_observable` rows with no reason recorded.
    """

    model_config = ConfigDict(frozen=True)

    units: tuple[str, ...]
    rows: tuple[CoverageRow, ...]
    missing_rows: tuple[str, ...]
    stale_rows: tuple[str, ...]
    duplicate_rows: tuple[str, ...]
    bad_classification: tuple[str, ...]
    missing_reason: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """True only when the table and the tree agree on every unit."""
        return not (
            self.missing_rows
            or self.stale_rows
            or self.duplicate_rows
            or self.bad_classification
            or self.missing_reason
        )

    def counts_by_classification(self) -> dict[str, int]:
        """Rows per bucket, so the split can be reported as a number, not an impression."""
        return {
            name: sum(1 for row in self.rows if row.classification == name)
            for name in sorted(CLASSIFICATIONS)
        }

    def failure_report(self) -> str:
        """Human-readable summary of every disagreement, empty when the gate is green."""
        problems = (
            ("unclassified units (add a row)", self.missing_rows),
            ("rows naming units that do not exist (delete the row)", self.stale_rows),
            ("units classified more than once", self.duplicate_rows),
            (f"classifications outside {sorted(CLASSIFICATIONS)}", self.bad_classification),
            (f"`{NOT_OBSERVABLE}` rows with no reason recorded", self.missing_reason),
        )
        lines = [f"{label}: {', '.join(names)}" for label, names in problems if names]
        return "\n".join(lines)
