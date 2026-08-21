"""
Module: retrieved_item
Layer: evals (eval harness — not part of src/)
Purpose: Frozen Pydantic v2 model representing one context item captured from
         GET /v1/admin/debug/retrieval for inclusion in generation transcripts.
Dependencies: pydantic
Used by: eval_records (evals/)

DEPRECATED as of the context receipt (item C3); kept for one release while
retrieval_join and the dashboard move over. Use GenerationRecord.context_receipt
(evals/context_receipt_record.py) instead.

Why: this is an *approximation* of the context that produced each engine reply. It
comes from a SECOND request — the debug endpoint re-runs retrieval with
session_turns=[] and flattens tier/priority metadata to sentinel values
(admin/debug_retrieval.py:80-108) — so precision computed over it is precision over
what the retriever RANKED, not over what reached the model. context_receipt is
produced by the assembly that actually served the turn and needs no second call.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RetrievedItem(BaseModel):
    """DEPRECATED: one context item from a second, session_turns=[] retrieval call.

    Superseded by ContextReceiptRecord; see this module's docstring.

    Mirrors ContextItemView from admin/debug_retrieval.py. Tier and priority default
    to sentinel values when not recoverable from the serialized prompt blob.

    Attributes:
        key: Top-level section key from the serialized context blob.
        tier: Context tier (sentinel 'unknown' when not recoverable from serialized form).
        priority: Context priority (sentinel 0 when not recoverable from serialized form).
        text: Full text of the context item.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    tier: str
    priority: int
    text: str
