"""
Module: retrieved_item
Layer: evals (eval harness — not part of src/)
Purpose: Frozen Pydantic v2 model representing one context item captured from
         GET /v1/admin/debug/retrieval for inclusion in generation transcripts.
Dependencies: pydantic
Used by: eval_records (evals/)

Note: This is an *approximation* of the context that produced each engine reply.
The debug endpoint re-runs retrieval with session_turns=[] and flattens tier/priority
metadata to sentinel values (admin/debug_retrieval.py:80-108). That caveat is
documented here rather than deferred.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RetrievedItem(BaseModel):
    """One context item from the retrieval pipeline, captured at generation time.

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
