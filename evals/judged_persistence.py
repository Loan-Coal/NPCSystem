"""
Module: judged_persistence
Layer: evals (eval harness — not part of src/)
Purpose: The single owner of the judged.jsonl row schema, for BOTH the
         single-judge path and the 3-model panel path. Every row — single-judge,
         panel consensus, or individual panel seat — is built by one function
         here, so the two paths cannot drift apart.
Dependencies: json, pathlib, typing; eval_records (GenerationRecord, JudgedRecord),
         judge_case_grouping (case_id_from_record_id), judge_panel (PanelScoredRecord)
Used by: judge_runner (single-judge + panel wiring)
Does NOT: call /v1/dialogue, modify graph state, import from src/npc_engine/

WHY THIS MODULE EXISTS (DEC-187)
The 2026-08-17 overnight panel run persisted a *different, poorer* row shape than
the single-judge writer: 6 fields instead of 8. It dropped `case_id`, `judge_kind`
and `repetition`, renamed `detail` to `error`, and derived `passed` as
`bool(score)` without consulting `expected_polarity`. Four separate downstream
defects (ISSUE-179 through ISSUE-181, plus ISSUE-175 going live) all trace back
to that one divergence. Centralising the schema here — with
tests/unit/evals/test_judged_persistence.py asserting the panel rows are a
superset of the single-judge rows — is the structural fix.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from eval_records import GenerationRecord, JudgedRecord
from judge_case_grouping import case_id_from_record_id
from judge_panel import PanelScoredRecord

_JSONL_ENCODING: str = "utf-8"

# expected_polarity values. A pass_on_yes record passes when the judge said YES;
# a pass_on_no record passes when the judge said NO (it did NOT affirm the lie).
_PASS_ON_YES: str = "pass_on_yes"

# judge_model value stamped on a consensus row, so a reader can tell a panel
# consensus verdict from a single named model's verdict without a second file.
_PANEL_MODEL_PREFIX: str = "panel:"


def apply_polarity(score: bool | None, expected_polarity: str) -> bool:
    """Map a raw YES/NO judge score to pass/fail using the record's polarity.

    This is the function whose absence inverted 135 of every judge's 345 rows in
    the 2026-08-17 panel run (ISSUE-179). An inconclusive score (None) is never a
    silent pass.

    Args:
        score: Raw judge verdict — True (YES), False (NO), None (infra failure).
        expected_polarity: 'pass_on_yes' or 'pass_on_no'.
    Returns:
        True when the record passed its expectation, else False.
    """
    if score is None:
        return False
    if expected_polarity == _PASS_ON_YES:
        return score is True
    return score is False


def _base_row(
    record: GenerationRecord,
    *,
    passed: bool,
    score: bool | None,
    detail: str,
    judge_model: str,
) -> dict:
    """Build the canonical judged.jsonl row shared by every writer here.

    Args:
        record: The record that was judged (supplies identity + repetition).
        passed: Polarity-applied verdict.
        score: Raw YES/NO judge verdict (None = infra failure).
        detail: Judge reasoning text.
        judge_model: Which model (or 'panel:N') produced the verdict.
    Returns:
        A row dict with the 8 canonical fields.
    """
    return {
        "record_id": record.record_id,
        "case_id": case_id_from_record_id(record.record_id),
        "judge_kind": record.judge_kind,
        "passed": passed,
        "score": score,
        "detail": detail,
        "judge_model": judge_model,
        "repetition": record.repetition,
    }


def judged_rows(judged_records: Sequence[JudgedRecord], judge_model: str) -> list[dict]:
    """Build single-judge rows — one per JudgedRecord.

    Args:
        judged_records: Scored records from a single-judge pass.
        judge_model: Name of the judge model used, recorded on every row so a
            transcript judged twice stays attributable (ISSUE-129 traceability).
    Returns:
        One row dict per record.
    """
    return [
        _base_row(
            r,
            passed=r.passed,
            score=r.score,
            detail=r.reasoning,
            judge_model=judge_model,
        )
        for r in judged_records
    ]


def consensus_rows(judged_records: Sequence[JudgedRecord], panel_size: int) -> list[dict]:
    """Build panel *consensus* rows — one per record, same shape as single-judge rows.

    This is what keeps `judged.jsonl` readable by every existing consumer
    (transcript_index.build_judged_index, label_import, compare, summary)
    unchanged after a panel run — the ISSUE-175 fix, option (b).

    Args:
        judged_records: Consensus JudgedRecords from judge_transcript_panel.
        panel_size: Number of seats, stamped into judge_model as 'panel:N'.
    Returns:
        One row dict per record.
    """
    return judged_rows(judged_records, judge_model=f"{_PANEL_MODEL_PREFIX}{panel_size}")


def seat_rows(scored: Sequence[PanelScoredRecord]) -> list[dict]:
    """Build per-seat vote rows — one per judge per record.

    A superset of the single-judge row: the 8 canonical fields plus
    `inconclusive`. Carrying `repetition` is what makes each of a k>1 run's
    repeats independently addressable (ISSUE-180); applying `expected_polarity`
    is what makes `passed` mean what it says (ISSUE-179).

    Args:
        scored: One PanelScoredRecord per judged record.
    Returns:
        len(verdicts) row dicts per record, in seat order.
    """
    rows: list[dict] = []
    for item in scored:
        polarity = item.record.expected_polarity
        for verdict in item.verdicts:
            row = _base_row(
                item.record,
                passed=apply_polarity(verdict.score, polarity),
                score=verdict.score,
                detail=verdict.error,
                judge_model=verdict.judge_model,
            )
            row["inconclusive"] = verdict.score is None
            rows.append(row)
    return rows


def _write_jsonl(rows: Sequence[dict], path: Path) -> None:
    """Write rows as JSONL, creating parent directories and overwriting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(row) for row in rows)
    path.write_text(body + "\n" if rows else "", encoding=_JSONL_ENCODING)


def write_judged_jsonl(
    judged_records: Sequence[JudgedRecord], path: Path, judge_model: str
) -> None:
    """Write single-judge rows to path (one row per record)."""
    _write_jsonl(judged_rows(judged_records, judge_model), path)


def write_consensus_jsonl(
    judged_records: Sequence[JudgedRecord], path: Path, panel_size: int
) -> None:
    """Write panel consensus rows to path (one row per record)."""
    _write_jsonl(consensus_rows(judged_records, panel_size), path)


def write_seat_votes_jsonl(scored: Sequence[PanelScoredRecord], path: Path) -> None:
    """Write per-seat vote rows to path (one row per judge per record)."""
    _write_jsonl(seat_rows(scored), path)
