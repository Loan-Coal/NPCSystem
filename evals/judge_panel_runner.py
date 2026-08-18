"""
Module: judge_panel_runner
Layer: evals (eval harness — not part of src/)
Purpose: Panel judge scoring (EVAL-P21.1/P21.2, DEC-183/184) — every judge_kind
         record is scored by every panel seat, consensus requires >=2-of-3 to
         fail (judge_panel.consensus_verdict), and every seat's verdict is
         returned paired with its record (judge_panel.PanelScoredRecord), not
         just the winning one. Split out of judge_runner.py to stay under the
         300-line cap. Persistence lives in judged_persistence, which owns the
         judged.jsonl schema for both the single-judge and panel paths (DEC-187).
         _apply_polarity here delegates to judged_persistence.apply_polarity —
         the shared implementation — but keeps its local name because
         judge_runner._apply_polarity is a named mutation-probe target
         (scripts/mutation_probe.py, locked EVAL-P15.6 spec) that must keep its
         exact name and location, so the two cannot simply be merged.
Dependencies: pathlib, typing; eval_records (GenerationRecord, JudgedRecord,
         read_transcript), judge_panel (run_panel, consensus_verdict,
         PanelVerdict, PanelScoredRecord), judged_persistence (apply_polarity)
Used by: judge_runner.py (--panel wiring)
Does NOT: call /v1/dialogue, modify graph state, import from src/npc_engine/
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from eval_records import GenerationRecord, JudgedRecord, read_transcript
from judge_panel import (
    PanelScoredRecord,
    PanelVerdict,
    _default_judge_fn,
    consensus_verdict,
    run_panel,
)
from judged_persistence import apply_polarity
from matchers import JudgeResult


def _apply_polarity(score: bool | None, polarity: str) -> bool:
    """Map a YES/NO judge score to pass/fail given the record's expected_polarity.

    Thin alias over judged_persistence.apply_polarity, the single shared
    implementation. Kept as a local name only because judge_runner._apply_polarity
    is a locked mutation-probe target and the two must stay separately addressable
    (see module docstring). score=None (infra failure) always yields False.
    """
    return apply_polarity(score, polarity)


def _panel_fail_votes(verdicts: Sequence[PanelVerdict], polarity: str) -> list[bool | None]:
    """Convert raw per-judge YES/NO verdicts into polarity-adjusted fail votes.

    judge_panel.consensus_verdict expects "did this judge vote fail" booleans
    (True=fail), but PanelVerdict.score is the raw YES/NO judge answer — the
    same value _apply_polarity operates on in the single-judge path. Applying
    the record's own polarity here, per seat, is required: a pass_on_yes
    record and a pass_on_no record disagree on whether score=True means the
    record passed, and feeding raw scores straight into consensus_verdict
    would silently invert the result for one of the two polarities.

    Args:
        verdicts: One record's PanelVerdicts, one per panel seat.
        polarity: The record's expected_polarity ("pass_on_yes"/"pass_on_no").
    Returns:
        One fail vote per verdict, in the same order: True=this judge says
        fail, False=this judge says pass, None=infra failure (unchanged).
    """
    return [
        None if v.score is None else not _apply_polarity(v.score, polarity)
        for v in verdicts
    ]


def _score_record_panel(
    record: GenerationRecord,
    models: Sequence[str],
    judge_fn: Callable[[str, str, str], JudgeResult],
) -> tuple[JudgedRecord, PanelScoredRecord]:
    """Score one GenerationRecord through every panel seat and apply consensus.

    Args:
        record: GenerationRecord with judge_kind != None.
        models: Panel roster to query, in seat order.
        judge_fn: Callable(model, criteria, content) -> JudgeResult; passed
            through to run_panel — injectable so tests never hit live Ollama.
    Returns:
        (JudgedRecord carrying the consensus verdict, a PanelScoredRecord
        pairing the record with every seat's raw verdict — persisted separately
        so every seat's opinion is auditable, not just the winning consensus).
    """
    verdicts = run_panel(
        record.record_id, record.criteria, record.npc_response,
        models=models, judge_fn=judge_fn,
    )
    fail_votes = _panel_fail_votes(verdicts, record.expected_polarity)
    consensus_fail, n_available = consensus_verdict(fail_votes)
    passed = not consensus_fail
    score: bool | None = passed if n_available > 0 else None
    reasoning = "; ".join(f"{v.judge_model}: {v.error}" for v in verdicts if v.error)
    judged = JudgedRecord(
        **record.model_dump(),
        passed=passed,
        score=score,
        reasoning=reasoning,
    )
    return judged, PanelScoredRecord(record=record, verdicts=tuple(verdicts))


def judge_transcript_panel(
    path: Path,
    models: Sequence[str],
    *,
    judge_fn: Callable[[str, str, str], JudgeResult] = _default_judge_fn,
) -> tuple[list[JudgedRecord], list[PanelScoredRecord]]:
    """Load a transcript and score every judge_kind record through the panel.

    Args:
        path: Path to a transcript file written by generate_runner.
        models: Panel roster to query, in seat order (see
            judge_config.resolve_judge_panel).
        judge_fn: Callable(model, criteria, content) -> JudgeResult; defaults
            to the live Ollama transport (judge_panel._default_judge_fn),
            injectable so tests never hit live Ollama.
    Returns:
        (judged_records — one consensus JudgedRecord per record, same shape
        judge_runner.judge_transcript returns, so group_by_case/summarize are
        unchanged; scored — one PanelScoredRecord per record, each pairing the
        record with its seats' raw verdicts. Returning records rather than a
        flat verdict list is deliberate: the flat list forced downstream code to
        re-derive grouping from record_id, which silently pooled a k>1 run's
        repetitions (ISSUE-181). See PanelScoredRecord's docstring.)
    """
    tf = read_transcript(path)
    judged_records: list[JudgedRecord] = []
    scored: list[PanelScoredRecord] = []
    for record in tf.records:
        if record.judge_kind is None:
            continue
        judged, item = _score_record_panel(record, models, judge_fn)
        judged_records.append(judged)
        scored.append(item)
    return judged_records, scored
