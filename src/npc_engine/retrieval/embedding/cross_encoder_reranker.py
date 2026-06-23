"""
Module: cross_encoder_reranker
Layer: retrieval
Purpose: Cross-encoder reranking of vector search results for improved Tier B/C relevance.
Does NOT: fetch graph data, call LLM services, or enforce token budgets.
Dependencies injected: None (model loaded on first call via lru_cache).
Used by: retrieval.context_builder (when CROSS_ENCODER_ENABLED=true)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .vector_store_protocol import VectorSearchResult

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _get_cross_encoder() -> Any:
    """Load and cache the cross-encoder model on first call.

    Downloads ~80 MB on first use; subsequent calls return the cached instance.
    Model is stored in the HuggingFace cache directory.
    """

    from sentence_transformers import CrossEncoder
    return CrossEncoder(_MODEL_NAME)


def rerank(query: str, candidates: list[VectorSearchResult]) -> list[VectorSearchResult]:
    """Rerank VectorSearchResult candidates by cross-encoder score against query.

    Uses a bi-directional cross-encoder (ms-marco-MiniLM-L-6-v2) to score each
    (query, candidate_text) pair. More accurate than bi-encoder cosine similarity
    but adds per-call inference latency (~100–500 ms on CPU, ~10–50 ms on GPU).

    Text is extracted from payload fields in priority order: summary → content → "".

    Args:
        query: The player message to score candidates against.
        candidates: Vector search results to rerank.

    Returns:
        Candidates reordered by descending cross-encoder score.
    """

    if not candidates:
        return candidates

    model = _get_cross_encoder()
    texts = [
        c["payload"].get("summary") or c["payload"].get("content") or ""
        for c in candidates
    ]
    scores = model.predict([(query, t) for t in texts])
    return [
        c
        for _, c in sorted(
            zip(scores, candidates),
            key=lambda pair: pair[0],
            reverse=True,
        )
    ]
