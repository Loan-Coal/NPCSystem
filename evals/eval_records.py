"""
Module: eval_records
Layer: evals (eval harness — not part of src/)
Purpose: Pydantic v2 record models for the two-phase generate→judge eval pipeline.
         GenerationRecord holds one engine reply + judge metadata; JudgedRecord
         adds the verdict; TranscriptFile bundles records for persist/replay.
Dependencies: pydantic, stdlib (pathlib, datetime, typing)
Used by: generate_runner, judge_runner, e2e/scenarios/conftest (persist_scenario_records)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRANSCRIPT_VERSION: int = 1


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
        expected_polarity: How to map the YES/NO judge verdict to pass/fail.
        world_epoch: World epoch at the time of generation (default age_of_peace).
        active_conditions: Active world conditions at the time of generation.
        metadata: Arbitrary extra data (e.g. expected_substrings for grounded checks).
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    source: Literal["runner", "anti_hallucination", "scenario"]
    npc_id: str
    player_id: str
    player_message: str
    npc_response: str
    criteria: str
    judge_kind: Literal["tone_judge", "affirms_judge", "refusal_judge"] | None
    expected_polarity: Literal["pass_on_yes", "pass_on_no"]
    world_epoch: str = "age_of_peace"
    active_conditions: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


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
        version: Schema version (always 1 today; increment on breaking change).
        generated_at: ISO-8601 timestamp of when the transcript was written.
        records: Ordered tuple of GenerationRecords from a single run.
    """

    model_config = ConfigDict(frozen=True)

    version: int = _TRANSCRIPT_VERSION
    generated_at: str
    records: tuple[GenerationRecord, ...]


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def write_transcript(path: Path, records: Sequence[GenerationRecord]) -> None:
    """Serialise records to a JSON transcript file.

    Creates parent directories if needed. Overwrites any existing file.

    Args:
        path: Destination file path (typically under e2e/transcripts/).
        records: Ordered sequence of GenerationRecords to persist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tf = TranscriptFile(
        generated_at=datetime.now(timezone.utc).isoformat(),
        records=tuple(records),
    )
    path.write_text(tf.model_dump_json(indent=2), encoding="utf-8")


def read_transcript(path: Path) -> TranscriptFile:
    """Load and validate a transcript file.

    Args:
        path: Path to a JSON file written by write_transcript.
    Returns:
        Validated TranscriptFile.
    Raises:
        ValidationError: If the file does not conform to the TranscriptFile schema.
        FileNotFoundError: If the path does not exist.
    """
    return TranscriptFile.model_validate_json(path.read_text(encoding="utf-8"))
