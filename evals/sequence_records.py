"""
Module: sequence_records
Layer: evals (eval harness — not part of src/)
Purpose: Frozen Pydantic v2 schema for multi-turn sequence transcripts.
         Defines SequenceRun, Repetition, Turn, ResetReceipt, and SequenceRunConfig
         — the v2 transcript record shape for multi-turn scenario evaluation.
Dependencies: pydantic, retrieved_item (evals/)
Used by: evals/sequence_runner.py (ResetReceipt, EVAL-P12.4), evals/sequence_fidelity.py
         (ResetReceipt), evals/sequence_runner_v2 (Turn/Repetition/SequenceRun,
         EVAL-P14 implementation, future)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from retrieved_item import RetrievedItem


class ResetReceipt(BaseModel):
    """Evidence of what a world reset actually cleared before one repetition.

    Every Repetition must carry a ResetReceipt so downstream statistics can
    distinguish independent repetitions (full reset) from correlated ones
    (partial reset) without assuming what reset_world() actually clears.

    Attributes:
        cleared: State component labels that were fully reset.
        surviving: State items that survived the reset (may correlate repeats).
        duration_ms: Wall-clock milliseconds the reset took.
    """

    model_config = ConfigDict(frozen=True)

    cleared: tuple[str, ...]
    surviving: tuple[str, ...]
    duration_ms: int


class Turn(BaseModel):
    """One message-response exchange within a multi-turn scenario repetition.

    Attributes:
        index: Zero-based position of this turn within the repetition.
        actor: Identity of the agent that sent the message (player id or NPC id).
        message: The input message sent to the NPC.
        response: The NPC's reply.
        world_epoch: World state epoch at the time of this turn.
        tick: Engine tick at the time of this turn.
        retrieved_context: Per-turn context items retrieved from the engine's
            retrieval pipeline, captured at turn execution time.
        duration_ms: Wall-clock milliseconds for this turn's engine call.
    """

    model_config = ConfigDict(frozen=True)

    index: int
    actor: str
    message: str
    response: str
    world_epoch: int
    tick: int
    retrieved_context: tuple[RetrievedItem, ...]
    duration_ms: int


class Repetition(BaseModel):
    """One full run of a multi-turn scenario within a k-repetition sequence.

    Attributes:
        index: Zero-based position of this repetition within the k-set.
        reset_receipt: Evidence of what was cleared before this repetition ran.
            Required — every repetition must record its own independence evidence
            rather than assuming the reset was complete.
        turns: Ordered sequence of Turn records for this repetition.
    """

    model_config = ConfigDict(frozen=True)

    index: int
    reset_receipt: ResetReceipt
    turns: tuple[Turn, ...]


class SequenceRunConfig(BaseModel):
    """Reproducibility snapshot for one sequence run.

    Carries only fields the sequence harness can populate without human
    intervention or external tool calls that may fail.

    Attributes:
        generation_model: LLM model name used for NPC response generation.
        git_sha: Short git commit hash at the time the run was started.
    """

    model_config = ConfigDict(frozen=True)

    generation_model: str
    git_sha: str


class SequenceRun(BaseModel):
    """Top-level transcript for one k-repetition run of one scenario.

    Attributes:
        run_id: Unique identifier for this run (e.g. 'run_20260810_001').
        scenario_id: Canonical scenario identifier (e.g. 'gossip_chain').
        k: Number of repetitions requested.
        config: Reproducibility snapshot for this run.
        repetitions: One Repetition per run, in execution order.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str
    scenario_id: str
    k: int
    config: SequenceRunConfig
    repetitions: tuple[Repetition, ...]
