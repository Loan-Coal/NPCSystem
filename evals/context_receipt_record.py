"""
Module: context_receipt_record
Layer: evals (eval harness — not part of src/)
Purpose: Frozen Pydantic v2 mirror of the engine's `context_receipt` response field —
         what ACTUALLY reached the model on one dialogue turn, stored on every
         GenerationRecord so a scored arm can be traced to the context that produced it.
Dependencies: pydantic, logging
Used by: transcript_models (GenerationRecord.context_receipt), generate_runner (capture)
Does NOT: call the engine, read files, or import from src/npc_engine — evals/ mirrors the
          response contract the same way retrieved_item mirrors ContextItemView.

This supersedes `retrieved_item.RetrievedItem`, which described a DIFFERENT assembly: it
came from a second call to GET /v1/admin/debug/retrieval with session_turns=[]. Precision
computed over that is precision over what the retriever RANKED; precision computed over
`item_keys` here is precision over what SURVIVED the prompt budget. Those can differ
sharply, because PROMPT_TOKEN_BUDGET currently derives to its clamp floor (RET-P0.3,
DEC-175, ISSUE-194).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = ["ContextReceiptRecord", "TierSpendRecord", "parse_context_receipt"]

_logger = logging.getLogger(__name__)


class TierSpendRecord(BaseModel):
    """What one context tier spent in the assembled prompt.

    Attributes:
        tier: Tier name as reported by the engine ('tier0', 'tierA', 'tierB', 'tierC').
        items: Number of items from this tier that reached the model.
        tokens: Estimated tokens those items occupied.
    """

    model_config = ConfigDict(frozen=True)

    tier: str
    items: int
    tokens: int


class ContextReceiptRecord(BaseModel):
    """The engine's report of one turn's context assembly, as stored in a transcript.

    Frozen: a receipt is evidence about a completed turn, so nothing downstream of
    generation may edit it.

    Attributes:
        retrieval_profile: Resolved profile name the turn ran under — the A/B arm.
        item_keys: Keys of the context items that reached the model.
        dropped_keys: Keys assembled and ranked but trimmed by the prompt token budget.
            The gap between this and item_keys is what the receipt exists to expose.
        tier_spend: Per-tier item and token spend.
        total_tokens: Estimated tokens across every tier that reached the model.
        prompt_token_budget: Budget the assembly was held to, recorded so a transcript
            read months later is interpretable without the Settings that produced it.
        budget_trimmed: Whether any assembled item failed to reach the model.
    """

    model_config = ConfigDict(frozen=True)

    retrieval_profile: str
    item_keys: tuple[str, ...] = Field(default=())
    dropped_keys: tuple[str, ...] = Field(default=())
    tier_spend: tuple[TierSpendRecord, ...] = Field(default=())
    total_tokens: int = 0
    prompt_token_budget: int = 0
    budget_trimmed: bool = False


def parse_context_receipt(payload: object) -> ContextReceiptRecord | None:
    """Parse the `context_receipt` block of a /v1/dialogue response body.

    Returns None rather than raising on a missing or malformed payload, and logs the
    reason: one bad turn must not abort an ~85-minute generation pass, but a receipt that
    silently vanished must still be distinguishable from a turn that reported none.
    None is also the honest value for a cached-context turn, which performed no assembly.

    Args:
        payload: The response body's `context_receipt` value, of any shape.
    Returns:
        A frozen ContextReceiptRecord, or None when absent or unparseable.
    """
    if not payload or not isinstance(payload, dict):
        return None
    try:
        return ContextReceiptRecord(**payload)
    except (ValidationError, TypeError) as exc:
        _logger.warning("context_receipt unparseable, storing None: %s", exc)
        return None
