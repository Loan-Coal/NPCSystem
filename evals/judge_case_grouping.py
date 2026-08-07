"""
Module: judge_case_grouping
Layer: evals (eval harness — not part of src/)
Purpose: Adapt JudgedRecords into summary.summarize()-compatible result dicts and
         group them back to one dict per (case_id, repetition), so a case with
         several judged expectations (e.g. a guard case's tone_judge + affirms_judge)
         contributes exactly one guard turn — not one per record (EVAL-P6.2, closes
         ISSUE-123: eval-judge previously reported 74 guard turns where make eval
         reported 37 for the same run). Split out of judge_runner.py to keep that
         module under the 300-line cap.
Dependencies: collections, typing; eval_records (JudgedRecord)
Used by: judge_runner (main's summarize/report path, and _write_judged_jsonl's
         case_id derivation)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from eval_records import JudgedRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RECORD_ID_COLON_SEGMENTS: int = 2


# ---------------------------------------------------------------------------
# case_id extraction
# ---------------------------------------------------------------------------


def case_id_from_record_id(record_id: str) -> str:
    """Strip the trailing ``:<judge_kind>:<index>`` segment off a record_id.

    Args:
        record_id: A GenerationRecord/JudgedRecord.record_id, of the form
            ``<case_id>:<judge_kind>:<index>``.
    Returns:
        The case_id prefix.
    """
    return record_id.rsplit(":", _RECORD_ID_COLON_SEGMENTS)[0]


# ---------------------------------------------------------------------------
# Result dict adapter
# ---------------------------------------------------------------------------


def to_result_dict(judged: JudgedRecord) -> dict:
    """Adapt a JudgedRecord to the result dict shape expected by summary.summarize.

    The shape mirrors runner._run_case output:
    {case_id, description, passed, expectations: [{kind, passed, skipped, detail}],
     response, error}.

    Args:
        judged: A scored JudgedRecord.
    Returns:
        Result dict consumable by summary.summarize and report.write_report.
    """
    exp_result: dict = {
        "kind": judged.judge_kind or "none",
        "passed": judged.passed,
        "skipped": False,
        "detail": judged.reasoning or "",
    }
    if judged.score is None:
        exp_result["inconclusive"] = True

    return {
        "case_id": judged.record_id,
        "description": f"[{judged.source}] {judged.npc_id}",
        "passed": judged.passed,
        "expectations": [exp_result],
        "response": {"npc_response": judged.npc_response},
        "error": None,
    }


# ---------------------------------------------------------------------------
# Case grouping (EVAL-P6.2 — closes ISSUE-123)
# ---------------------------------------------------------------------------


def group_by_case(judged_records: Sequence[JudgedRecord]) -> list[dict]:
    """Merge per-record result dicts back to one dict per (case_id, repetition).

    A guard case that injects both tone_judge and affirms_judge expectations
    (runner._guard_expectations, every demo-world guard case) produces two
    JudgedRecords sharing one case_id. Feeding both straight to summary.summarize
    counts two guard turns for one case (ISSUE-123: 74 vs make eval's 37).
    Grouping by (case_id, repetition) — not case_id alone — keeps this correct
    once k-repeat runs land (EVAL-P6.4): each repetition of a case is still one
    turn, but the turn's expectations are merged into a single result dict, the
    same multi-expectation-per-case shape runner._run_case already produces.

    Args:
        judged_records: Scored records from a judge pass (any case, any repetition).
    Returns:
        One result dict per (case_id, repetition), in first-seen order, each with
        every contributing record's expectation entry under "expectations".
    """
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for record in judged_records:
        key = (case_id_from_record_id(record.record_id), record.repetition)
        groups[key].append(to_result_dict(record))

    merged: list[dict] = []
    for (case_id, _rep), result_dicts in groups.items():
        merged.append(
            {
                "case_id": case_id,
                "description": result_dicts[0]["description"],
                "passed": all(r["passed"] for r in result_dicts),
                "expectations": [r["expectations"][0] for r in result_dicts],
                "response": result_dicts[0]["response"],
                "error": None,
            }
        )
    return merged
