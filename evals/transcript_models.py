"""
Module: transcript_models
Layer: evals (eval harness — not part of src/)
Purpose: The Pydantic v2 record models and shared constants of the two-phase
         generate→judge transcript schema (v2, EVAL-P1.3). Split out of
         eval_records.py, which exceeded the 300-line cap once EVAL-P18.1 added
         harness_version handling; that module keeps the persistence functions
         and re-exports every name here, so `from eval_records import ...`
         is unchanged for all existing callers.
Dependencies: pydantic, stdlib (logging, typing); context_receipt_record
         (ContextReceiptRecord), retrieved_item (RetrievedItem), run_config (RunConfig)
Used by: eval_records (re-export); anything importing the record models
Does NOT: read or write files — persistence lives in eval_records
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from context_receipt_record import ContextReceiptRecord
from retrieved_item import RetrievedItem
from run_config import RunConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRANSCRIPT_VERSION: int = 2
_logger = logging.getLogger(__name__)

# Sentinel harness_version for gen-dirs written before EVAL-P18.1 (2026-08-12)
# made the field required on RunConfig. Explicit and visibly non-comparable
# (never matches a real resolve_harness_version() hash) rather than a silent
# default on RunConfig itself — see ISSUE-152: a default there would let two
# incomparable runs compare cleanly by accident.
LEGACY_HARNESS_VERSION: str = "legacy_pre_p18_1"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TranscriptVersionError(ValueError):
    """Raised when a transcript file has an unsupported schema version.

    Attributes:
        found: The version number found in the file.
        expected: The version number this reader requires.
    """

    def __init__(self, *, found: int, expected: int) -> None:
        self.found = found
        self.expected = expected
        super().__init__(
            f"Transcript version mismatch: found {found}, expected {expected}. "
            f"This reader requires version {expected}; v{found} transcripts are not supported."
        )


# ---------------------------------------------------------------------------
# Deterministic matcher kinds (EVAL-P6.1)
# ---------------------------------------------------------------------------

# Every non-judge matcher kind evaluable off a transcript, plus the grounded
# anti-hallucination check (not a matchers.py kind, but scored the same way —
# no LLM call, replayed from stored metadata). Single source of truth: both
# GenerationRecord.matcher_kind and deterministic_records.covered_matcher_kinds()
# derive from this alias so the two can never drift apart silently.
DeterministicMatcherKind = Literal[
    "schema",
    "min_length",
    "keyword_any",
    "keyword_all",
    "keyword_none",
    "in_set",
    "range",
    "substring",
    "regex",
    "context_block_expected",
    "anti_hallucination_grounded",
]


# ---------------------------------------------------------------------------
# Record models
# ---------------------------------------------------------------------------


class GenerationRecord(BaseModel):
    """One engine reply plus the metadata needed to judge it later.

    Frozen so records are immutable once created — safe to cache and serialize.

    Attributes:
        record_id: Stable ID of the form ``<case_id>:<judge_kind>:<index>``.
        source: Which runner produced this record.
        npc_id: Character that produced the npc_response.
        player_id: Player interacting with the NPC.
        player_message: The player's dialogue turn.
        npc_response: The engine reply to evaluate.
        criteria: Verbatim criteria string for _run_binary_judge.
        judge_kind: Which judge function to apply, or None for deterministic checks.
        matcher_kind: Which deterministic matcher applies when judge_kind is None
            (e.g. 'min_length', 'schema'). None for judge-based records and for
            records written before EVAL-P6.1.
        expected_polarity: How to map the YES/NO judge verdict to pass/fail.
        active_conditions: Active world conditions at the time of generation.
        metadata: Arbitrary extra data. Deterministic records (matcher_kind set)
            store {"expectation": <raw expectation dict>, "response": <raw API
            response dict>} here so deterministic_records.score_record can replay
            the matcher without re-calling the engine; anti_hallucination_grounded
            records store {"expected_fact_substrings": [...], "response": {...}}.
        repetition: Zero-based repeat index within a k-repeat run (default 0).
        duration_ms: Wall-clock milliseconds taken to generate npc_response (default 0).
        retrieved_context: DEPRECATED (kept for one release). Context items captured
            from a SECOND call to GET /v1/admin/debug/retrieval with session_turns=[],
            so it describes a different assembly than the one that produced
            npc_response. Use context_receipt instead — see RetrievedItem's docstring.
        context_receipt: What the engine reports ACTUALLY reached the model for this
            turn: resolved retrieval profile, the context keys assembled, per-tier token
            spend, and whether the prompt budget trimmed anything. Defaults to None so
            corpora written before this field (evals/generations/k3_73e6c36/) still load,
            and None is also the honest value for a cached-context turn.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    source: Literal["runner", "anti_hallucination", "scenario"]
    npc_id: str
    player_id: str
    player_message: str
    npc_response: str
    criteria: str
    # "refusal_judge" is retired (measurement-remediation Phase 2c, DEC-269 — folded
    # into affirms_judge via matchers.judge_affirms) and no longer produced by any
    # writer, but stays a valid Literal member so the 150 refusal_judge rows already
    # committed in evals/generations/{k3_73e6c36,k3_77688e7_regen1}/judged.jsonl stay
    # parseable through this model if anything ever re-validates them, rather than
    # only by coincidence of every current reader using raw json.loads instead.
    judge_kind: (
        Literal["tone_judge", "liveness_judge", "affirms_judge", "commits_judge", "refusal_judge"]
        | None
    )
    matcher_kind: DeterministicMatcherKind | None = None
    expected_polarity: Literal["pass_on_yes", "pass_on_no"]
    active_conditions: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    repetition: int = 0
    duration_ms: int = 0
    retrieved_context: tuple[RetrievedItem, ...] = ()
    context_receipt: ContextReceiptRecord | None = None


class JudgedRecord(GenerationRecord):
    """A GenerationRecord augmented with the judge's verdict.

    Attributes:
        passed: Whether the record met its expectation after polarity is applied.
        score: Raw YES/NO verdict from the judge (None = infra failure/inconclusive).
        reasoning: Judge's reasoning text (empty string when score is True).
    """

    passed: bool
    score: bool | None
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Transcript file model
# ---------------------------------------------------------------------------


class TranscriptFile(BaseModel):
    """A bundle of GenerationRecords written during a generate pass.

    Attributes:
        version: Schema version (2 as of EVAL-P1.3; read_transcript rejects v1 loudly).
        generated_at: ISO-8601 timestamp of when the transcript was written.
        gen_id: Identifier for this generation run (e.g. 'smoke-001'). Empty when
            the transcript was written by a pre-EVAL-P1.4 runner.
        k: Number of repetitions per case in this run. Defaults to 1.
        config: Exact reproducibility snapshot for this run. None when the transcript
            was written by a pre-EVAL-P1.4 runner.
        records: Ordered tuple of GenerationRecords from a single run.
    """

    model_config = ConfigDict(frozen=True)

    version: int = _TRANSCRIPT_VERSION
    generated_at: str
    gen_id: str = ""
    k: int = 1
    config: RunConfig | None = None
    records: tuple[GenerationRecord, ...]


