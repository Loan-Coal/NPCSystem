"""
Module: trend_store
Layer: evals (eval harness — not part of src/)
Purpose: Append-only JSONL trend storage — one row per run, keyed by gen_id.
         The metrics-contract item 4 store ("trend across runs plus a
         regression alert that exits non-zero on a drop"): today `compare`
         is strictly A-vs-B and nothing aggregates across runs, so "is the
         engine improving over six weeks" is currently unanswerable. This
         module is the append-only history regression_gate.py (EVAL-P23.2)
         and Run-EvalHarness.ps1 (EVAL-P23.3) read from.
Dependencies: pydantic, pathlib, typing
Used by: tests/unit/evals/test_trend_store.py; scripts/Run-EvalHarness.ps1
         (records a row after every harness run, EVAL-P23.3)
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict

TREND_STORE_FILE: Path = Path(__file__).parent / "trend" / "trend_v1.jsonl"


class DuplicateGenIdError(ValueError):
    """Raised when a gen_id already has a recorded trend row.

    Attributes:
        gen_id: The generation id that was already present.
    """

    def __init__(self, gen_id: str) -> None:
        self.gen_id = gen_id
        super().__init__(
            f"gen_id {gen_id!r} already has a trend row — this store is "
            "append-only. A run's numbers do not change after it is "
            "recorded; re-run the harness against a new gen_id instead of "
            "overwriting history."
        )


class RateWithCI(BaseModel):
    """One published rate with its Wilson CI and denominator.

    Attributes:
        rate: Pass rate; None when the denominator (n) was 0.
        ci_low: Lower 95% Wilson CI bound; None when rate is None.
        ci_high: Upper 95% Wilson CI bound; None when rate is None.
        n: The denominator this rate was computed over.
    """

    model_config = ConfigDict(frozen=True)

    rate: float | None
    ci_low: float | None
    ci_high: float | None
    n: int


class ScorerKappa(BaseModel):
    """One scorer's Cohen's kappa with its bootstrap CI.

    Attributes:
        scorer: The scorer name (e.g. 'tone_judge').
        kappa: Point estimate.
        ci_low: Lower bound of the seeded cluster-bootstrap CI.
        ci_high: Upper bound of the seeded cluster-bootstrap CI.
        n: Adjudicated rows the kappa was computed over.
    """

    model_config = ConfigDict(frozen=True)

    scorer: str
    kappa: float
    ci_low: float
    ci_high: float
    n: int


class TrendRow(BaseModel):
    """One run's published numbers — the unit this store appends.

    extra="allow" so a row written by a newer harness version (carrying a
    field this reader doesn't know about) still loads instead of raising;
    every field below except gen_id/harness_version/recorded_at has a
    default so a row written by an OLDER harness version — before that
    field existed — also still loads.

    Attributes:
        gen_id: The generation this row's numbers were measured against.
            The store's key — re-recording one is refused (see
            DuplicateGenIdError). A run's numbers must not silently change
            after the fact.
        harness_version: Identifies which code produced these numbers, so a
            harness change is visible in the trend rather than looking like
            engine drift.
        recorded_at: ISO-8601 timestamp of when this row was appended.
        guard: Guard battery rate with CI and n; None when no guard turns ran.
        capability: Capability battery rate with CI and n; None when none ran.
        inconclusive_rate: Fraction of judged expectations that returned
            score=None (infra failure) rather than a real verdict.
        scorer_kappas: Every calibrated scorer's kappa for this run.
        panel_agreement_rate: Inter-judge pairwise agreement rate, when the
            panel judge ran (EVAL-P21.2); None otherwise.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    gen_id: str
    harness_version: str
    recorded_at: str
    guard: RateWithCI | None = None
    capability: RateWithCI | None = None
    inconclusive_rate: float | None = None
    scorer_kappas: tuple[ScorerKappa, ...] = ()
    panel_agreement_rate: float | None = None


def read_trend_rows(path: Path = TREND_STORE_FILE) -> list[TrendRow]:
    """Load every trend row from the store, in file (append) order.

    Args:
        path: Trend store JSONL path.
    Returns:
        Rows in the order they were appended, or [] when the file doesn't exist.
    Raises:
        ValidationError: If any line does not conform to TrendRow's required fields.
    """
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [TrendRow.model_validate_json(line) for line in lines if line.strip()]


def append_trend_row(row: TrendRow, path: Path = TREND_STORE_FILE) -> None:
    """Append one trend row, refusing to duplicate an existing gen_id.

    Args:
        row: The TrendRow to append.
        path: Trend store JSONL path.
    Raises:
        DuplicateGenIdError: If row.gen_id already has a row in the store.
    """
    existing = read_trend_rows(path)
    if any(r.gen_id == row.gen_id for r in existing):
        raise DuplicateGenIdError(row.gen_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(row.model_dump_json() + "\n")


def latest_row(path: Path = TREND_STORE_FILE) -> TrendRow | None:
    """Return the most recently appended trend row, or None if the store is empty.

    Args:
        path: Trend store JSONL path.
    Returns:
        The last row in the store, or None when no rows exist. This is the
        baseline regression_gate.py compares a new run's numbers against —
        "most recently recorded" not "highest-numbered" or "best": trend
        rows are strictly append-ordered and never reordered.
    """
    rows = read_trend_rows(path)
    return rows[-1] if rows else None


def rows_for_scorer(scorer: str, rows: Sequence[TrendRow]) -> list[ScorerKappa]:
    """Extract one scorer's kappa across a sequence of trend rows.

    Args:
        scorer: The scorer name to filter for.
        rows: Trend rows to search (e.g. read_trend_rows()'s output).
    Returns:
        That scorer's ScorerKappa from every row that calibrated it, in the
        rows' own order — rows where the scorer wasn't calibrated yet
        (too few adjudicated rows at the time) are silently absent rather
        than padded with a fabricated value.
    """
    return [k for row in rows for k in row.scorer_kappas if k.scorer == scorer]
