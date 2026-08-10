"""
Module: oracle_matrix
Layer: scripts (dev tooling — not part of src/ or the evals package)
Purpose: The data model and the pure labelling rule behind the oracle labeller —
         the requested confusion matrix, the per-cell caps the artifact imposes,
         the named error raised when a request exceeds them, and the
         deterministic assignment of pre_labels that reproduces the matrix.
Dependencies: pathlib, typing, pydantic
Used by: scripts/oracle_labeller.py (reads artifacts, then calls this),
         tests/unit/evals/test_oracle_labeller.py (via oracle_labeller re-exports)
Does NOT: read or write any file, call any LLM, or use randomness.

Split out of oracle_labeller.py to stay under the 300-line cap and to keep the
rule (pure, testable, no I/O) separate from the reader and CLI around it.
See the DECLARED RULE section of oracle_labeller.py's docstring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict

_NOTE_PREFIX: str = "ORACLE:"
_NOTE_MAX_CHARS: int = 140


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RequestedMatrix(BaseModel):
    """A 2×2 confusion matrix requested of the oracle (scorer_verdict × human_verdict).

    Attributes:
        tp: scorer_verdict=True, human_verdict=True.
        fp: scorer_verdict=True, human_verdict=False.
        fn: scorer_verdict=False, human_verdict=True.
        tn: scorer_verdict=False, human_verdict=False.
    """

    model_config = ConfigDict(frozen=True)

    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def positives_needed(self) -> int:
        """Rows the request needs from the scorer_verdict=True partition."""
        return self.tp + self.fp

    @property
    def negatives_needed(self) -> int:
        """Rows the request needs from the scorer_verdict=False partition."""
        return self.fn + self.tn


class MatrixCaps(BaseModel):
    """Per-cell ceilings imposed by the rows that actually exist for one scorer.

    Attributes:
        scorer: The scorer these caps were measured for.
        positives_available: Rows with scorer_verdict=True.
        negatives_available: Rows with scorer_verdict=False.
    """

    model_config = ConfigDict(frozen=True)

    scorer: str
    positives_available: int
    negatives_available: int

    def cannot_satisfy(self, requested: RequestedMatrix) -> bool:
        """Return True when `requested` needs more rows than exist."""
        return (
            requested.positives_needed > self.positives_available
            or requested.negatives_needed > self.negatives_available
        )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnsatisfiableMatrixError(Exception):
    """Raised when a requested matrix needs more rows than the artifact holds.

    Emitting a *different* matrix silently would make the whole instrument
    worthless: the point of the oracle is that the number is known in advance.

    Attributes:
        requested: The matrix that cannot be built.
        caps: The ceilings that make it impossible.
    """

    def __init__(self, requested: RequestedMatrix, caps: MatrixCaps) -> None:
        self.requested = requested
        self.caps = caps
        super().__init__(
            f"Requested matrix is unsatisfiable for scorer {caps.scorer!r}.\n"
            f"  tp+fp requested {requested.positives_needed}, "
            f"scorer_verdict=True rows available {caps.positives_available}\n"
            f"  fn+tn requested {requested.negatives_needed}, "
            f"scorer_verdict=False rows available {caps.negatives_available}\n"
            f"  per-cell caps: tp<={caps.positives_available}, fp<={caps.positives_available}, "
            f"fn<={caps.negatives_available}, tn<={caps.negatives_available}"
        )


class OracleOutputPathError(Exception):
    """Raised when the oracle is aimed at the real human labels file.

    Attributes:
        out_path: The refused destination.
    """

    def __init__(self, out_path: Path) -> None:
        self.out_path = out_path
        super().__init__(
            f"Refusing to write oracle output to {out_path} — that is the real "
            f"human labels file. Its verdicts cannot be regenerated."
        )


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------


def partition_by_verdict(
    items: Sequence[dict[str, Any]],
    verdicts: dict[str, bool],
    scorer: str,
) -> tuple[list[str], list[str]]:
    """Split one scorer's item ids into (scorer_verdict=True, scorer_verdict=False).

    Both partitions are sorted by item id, so the rule is deterministic with no
    RNG anywhere.

    Args:
        items: Export batch items.
        verdicts: item_id→scorer_verdict index.
        scorer: Target scorer name.
    Returns:
        (positive item ids, negative item ids), each sorted.
    """
    positives: list[str] = []
    negatives: list[str] = []
    for item in items:
        if item.get("scorer") != scorer:
            continue
        item_id = str(item["record_id"])
        if item_id not in verdicts:
            continue
        (positives if verdicts[item_id] else negatives).append(item_id)
    return sorted(positives), sorted(negatives)


def _row(item_id: str, scorer: str, pre_label: bool) -> dict[str, Any]:
    note = f"{_NOTE_PREFIX} rule-based label for {scorer}; not a human judgment"
    return {
        "record_id": item_id,
        "scorer": scorer,
        "pre_label": pre_label,
        "notes": note[:_NOTE_MAX_CHARS],
    }


def assign_labels(
    positives: Sequence[str],
    negatives: Sequence[str],
    scorer: str,
    requested: RequestedMatrix,
) -> list[dict[str, Any]]:
    """Apply the declared rule to pre-partitioned item ids.

    Args:
        positives: Sorted item ids with scorer_verdict=True.
        negatives: Sorted item ids with scorer_verdict=False.
        scorer: Target scorer name.
        requested: The matrix to reproduce.
    Returns:
        Exactly tp+fp+fn+tn raw label rows. Leftover ids are omitted, because a
        row outside the requested matrix would perturb the known result.
    """
    rows = [_row(i, scorer, True) for i in positives[: requested.tp]]
    rows += [
        _row(i, scorer, False)
        for i in positives[requested.tp : requested.positives_needed]
    ]
    rows += [_row(i, scorer, True) for i in negatives[: requested.fn]]
    rows += [
        _row(i, scorer, False)
        for i in negatives[requested.fn : requested.negatives_needed]
    ]
    return rows
