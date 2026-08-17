"""
Module: judge_panel_runner
Layer: evals (eval harness — not part of src/)
Purpose: Panel judge scoring (EVAL-P21.1/P21.2, DEC-183/184) — every judge_kind
         record is scored by every panel seat, consensus requires >=2-of-3 to
         fail (judge_panel.consensus_verdict), and every seat's verdict is
         persisted (judge_panel.to_judged_rows), not just the winning one.
         Split out of judge_runner.py to stay under the 300-line cap.
         _apply_polarity here deliberately mirrors judge_runner._apply_polarity
         rather than importing it: judge_runner.py imports this module for
         --panel wiring, so importing the other way would be circular, and
         judge_runner._apply_polarity is a named mutation-probe target
         (scripts/mutation_probe.py, locked EVAL-P15.6 spec) that must keep
         its exact name and location.
Dependencies: json, pathlib, typing; eval_records (GenerationRecord, JudgedRecord,
         read_transcript), judge_panel (run_panel, to_judged_rows, consensus_verdict,
         pairwise_agreement, PanelVerdict, AgreementResult)
Used by: judge_runner.py (--panel wiring)
Does NOT: call /v1/dialogue, modify graph state, import from src/npc_engine/
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Sequence

from eval_records import GenerationRecord, JudgedRecord, read_transcript
from judge_panel import (
    AgreementResult,
    PanelVerdict,
    _default_judge_fn,
    consensus_verdict,
    pairwise_agreement,
    run_panel,
    to_judged_rows,
)
from matchers import JudgeResult

_PASS_ON_YES: str = "pass_on_yes"
_JSONL_ENCODING: str = "utf-8"


def _apply_polarity(score: bool | None, polarity: str) -> bool:
    """Map a YES/NO judge score to pass/fail given the record's expected_polarity.

    Kept in sync with judge_runner._apply_polarity — same truth table,
    duplicated rather than imported to avoid a circular import (see module
    docstring). score=None (infra failure) always yields False.
    """
    if score is None:
        return False
    if polarity == _PASS_ON_YES:
        return score is True
    return score is False  # pass_on_no: NO verdict = did not affirm = PASS


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
) -> tuple[JudgedRecord, list[PanelVerdict]]:
    """Score one GenerationRecord through every panel seat and apply consensus.

    Args:
        record: GenerationRecord with judge_kind != None.
        models: Panel roster to query, in seat order.
        judge_fn: Callable(model, criteria, content) -> JudgeResult; passed
            through to run_panel — injectable so tests never hit live Ollama.
    Returns:
        (JudgedRecord carrying the consensus verdict, the raw per-seat
        PanelVerdicts — persisted separately so every seat's opinion is
        auditable, not just the winning consensus).
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
    return judged, verdicts


def judge_transcript_panel(
    path: Path,
    models: Sequence[str],
    *,
    judge_fn: Callable[[str, str, str], JudgeResult] = _default_judge_fn,
) -> tuple[list[JudgedRecord], list[PanelVerdict]]:
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
        unchanged; all_verdicts — every seat's raw verdict for every record,
        in per-record-contiguous order, for to_judged_rows persistence and
        pairwise_agreement).
    """
    tf = read_transcript(path)
    judged_records: list[JudgedRecord] = []
    all_verdicts: list[PanelVerdict] = []
    for record in tf.records:
        if record.judge_kind is None:
            continue
        judged, verdicts = _score_record_panel(record, models, judge_fn)
        judged_records.append(judged)
        all_verdicts.extend(verdicts)
    return judged_records, all_verdicts


def write_panel_judged_jsonl(verdicts: Sequence[PanelVerdict], path: Path) -> None:
    """Write one JSONL row per judge per record — every seat's own verdict.

    Deliberately a different row shape from judge_runner._write_judged_jsonl's
    single-judge rows (record_id, judge_model, score, passed, inconclusive,
    error — see judge_panel.to_judged_rows): panel mode's judged.jsonl is one
    file with len(models) rows per record_id, not one. Anything reading
    judged.jsonl that assumes one row per record_id (e.g.
    transcript_index.build_judged_index) must be updated before consuming
    panel-mode output — see ISSUE-175.

    Args:
        verdicts: Every seat's PanelVerdict across the whole transcript.
        path: Destination .jsonl file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = to_judged_rows(verdicts)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding=_JSONL_ENCODING,
    )


def panel_agreement_from_verdicts(verdicts: Sequence[PanelVerdict]) -> AgreementResult:
    """Compute inter-judge pairwise agreement across a panel run's verdicts.

    Groups verdicts by record_id (each record's seats stay in run order,
    matching judge_transcript_panel's per-record-contiguous emission) and
    feeds the per-record vote lists to judge_panel.pairwise_agreement.

    Args:
        verdicts: Every seat's PanelVerdict across the whole transcript.
    Returns:
        AgreementResult summarising pairwise agreement across all records.
    """
    votes_by_record: dict[str, list[bool | None]] = {}
    for v in verdicts:
        votes_by_record.setdefault(v.record_id, []).append(v.score)
    return pairwise_agreement(list(votes_by_record.values()))
