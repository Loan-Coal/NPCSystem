"""
Module: baseline_selection
Layer: evals (eval harness — not part of src/)
Purpose: Decide WHICH prior trend row a candidate run is gated against, and say
         so out loud. One baseline is resolved once and used by both the
         informational compare step and the authoritative trend gate, so the
         per-case delta table and the verdict can never describe different
         comparisons (EVAL-P23 Defect A/B).
Dependencies: datetime, typing, pydantic; trend_store (TrendRow,
         latest_comparable_row)
Used by: scripts/record_trend_and_gate.py (both the --print-baseline resolution
         the PowerShell harness calls before its compare step, and the gate that
         follows it)
Does NOT: decide whether anything regressed — regression_gate and
         instrument_gate own the verdicts; this module only picks the pair.

WHY THE CHOICE IS NARRATED, NOT JUST MADE
Walking back past incomparable rows is the right behaviour, but silently
comparing against a run from six weeks ago is not meaningfully better than
silently comparing against an incomparable one. Every caller therefore prints
format_baseline_choice's line: the gen_id, how many rows back it sits, how many
rows were skipped, and how old it is.
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from pydantic import BaseModel, ConfigDict

from trend_store import TrendRow

_SECONDS_PER_DAY: float = 86400.0


class BaselineChoice(BaseModel):
    """The baseline a gate will use, or the reason there isn't one.

    Attributes:
        row: The chosen baseline row; None when nothing comparable exists.
        rows_back: How far back the chosen row sits, counting from the end of
            the store (1 = the immediately preceding row). 0 when none chosen.
        skipped: Rows walked past because their harness_version differed.
        harness_version: The version comparability was required against.
        refusal: Why no row was chosen; empty when one was.
    """

    model_config = ConfigDict(frozen=True)

    row: TrendRow | None = None
    rows_back: int = 0
    skipped: int = 0
    harness_version: str = ""
    refusal: str = ""


def _position(gen_id: str, rows: Sequence[TrendRow]) -> tuple[int, int]:
    """Return (rows_back, skipped) for the chosen row's place in the store."""
    for offset, row in enumerate(reversed(rows), start=1):
        if row.gen_id == gen_id:
            return offset, offset - 1
    return 0, 0


def _no_comparable_row_message(harness_version: str, total: int) -> str:
    """Explain a refusal in terms of what the maintainer must do next."""
    if total == 0:
        return (
            "the trend store is empty, so there is no baseline to gate against. "
            "Record this run with --allow-no-baseline to establish one."
        )
    return (
        f"{total} trend row(s) exist but none was recorded under "
        f"harness_version={harness_version}. harness_version hashes evals/cases/, "
        "prompts/eval/ and matchers.py, so a case or judge-criterion edit makes "
        "older rows incomparable — compare.py refuses the same pair, and gating "
        "on it would be a confident verdict about two different instruments. "
        "Re-record a baseline under this harness_version before gating."
    )


def select_baseline(harness_version: str, rows: Sequence[TrendRow]) -> BaselineChoice:
    """Pick the most recent comparable row, walking back past incomparable ones.

    Args:
        harness_version: The candidate run's harness_version.
        rows: The trend store's rows in append order.
    Returns:
        A BaselineChoice naming the chosen row and its position, or one whose
        `refusal` explains why nothing was comparable. Refusal is reserved for
        there being no comparable row at all — a slightly older comparable
        baseline is still a real baseline, and is reported as such.
    """
    for offset, row in enumerate(reversed(rows), start=1):
        if row.harness_version == harness_version:
            return BaselineChoice(
                row=row, rows_back=offset, skipped=offset - 1, harness_version=harness_version
            )
    return BaselineChoice(
        harness_version=harness_version,
        refusal=_no_comparable_row_message(harness_version, len(rows)),
    )


def select_named_baseline(
    gen_id: str, harness_version: str, rows: Sequence[TrendRow]
) -> BaselineChoice:
    """Pick one explicitly named row, refusing it when it is not comparable.

    An explicit override exists so a human can pin both the compare step and the
    gate to the same pair — not so comparability can be bought past. A named row
    from another harness_version is refused exactly as an implicit one would be.

    Args:
        gen_id: The trend row explicitly requested.
        harness_version: The candidate run's harness_version.
        rows: The trend store's rows in append order.
    Returns:
        A BaselineChoice naming that row, or one whose `refusal` says whether it
        was absent or incomparable.
    """
    match = next((r for r in rows if r.gen_id == gen_id), None)
    if match is None:
        return BaselineChoice(
            harness_version=harness_version,
            refusal=f"no trend row has gen_id={gen_id!r}; it has not been recorded in this store.",
        )
    if match.harness_version != harness_version:
        return BaselineChoice(
            harness_version=harness_version,
            refusal=(
                f"trend row {gen_id!r} was recorded under "
                f"harness_version={match.harness_version!r}, but this run is "
                f"{harness_version!r}. Naming a baseline explicitly does not make it "
                "comparable — re-record a baseline under this harness_version."
            ),
        )
    rows_back, skipped = _position(gen_id, rows)
    return BaselineChoice(
        row=match, rows_back=rows_back, skipped=skipped, harness_version=harness_version
    )


def _age_phrase(baseline_recorded_at: str, candidate_recorded_at: str) -> str:
    """Render 'N.N days older', or an empty string when either stamp is unparseable."""
    try:
        older = datetime.fromisoformat(baseline_recorded_at)
        newer = datetime.fromisoformat(candidate_recorded_at)
    except ValueError:
        return ""  # quality-ok: an uncomputable age degrades the line, never the gate
    return f"{(newer - older).total_seconds() / _SECONDS_PER_DAY:.1f} days older, "


def format_baseline_choice(choice: BaselineChoice, candidate_recorded_at: str) -> str:
    """Render the chosen baseline (or the refusal) as one console line.

    Args:
        choice: The BaselineChoice to describe.
        candidate_recorded_at: The candidate run's ISO-8601 timestamp, used to
            state how much older the baseline is.
    Returns:
        A single line naming the baseline's gen_id, how far back it sits, how
        many incomparable rows were skipped and how old it is — so comparing
        against a much older run is visible rather than silent — or
        "NO COMPARABLE BASELINE: <reason>" when none was chosen.
    """
    if choice.row is None:
        return f"NO COMPARABLE BASELINE: {choice.refusal}"
    return (
        f"Baseline: gen_id={choice.row.gen_id} "
        f"({choice.rows_back} row(s) back, skipped {choice.skipped} incomparable, "
        f"{_age_phrase(choice.row.recorded_at, candidate_recorded_at)}"
        f"recorded {choice.row.recorded_at}, harness_version={choice.row.harness_version})"
    )
