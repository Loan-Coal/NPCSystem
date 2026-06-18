"""
Module: retrieval_matchers
Layer: evals (evaluation harness)
Purpose: Pure metric functions for information-retrieval evaluation — precision@k, recall@k, MRR.
Dependencies: none (pure Python, no I/O)
Used by: evals.retrieval_runner, tests.unit.test_retrieval_eval
"""

from __future__ import annotations


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Compute Precision@k: fraction of top-k results that are relevant.

    Args:
        ranked: Ordered list of retrieved item IDs (most-relevant first).
        relevant: Set of ground-truth relevant item IDs.
        k: Number of top results to evaluate.  If k<=0 or ranked is empty, returns 0.0.

    Returns:
        Float in [0.0, 1.0].  0.0 when k==0 or no items retrieved.
    """
    if k <= 0 or not ranked:
        return 0.0
    top_k = ranked[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(top_k)


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Compute Recall@k: fraction of relevant items that appear in the top-k results.

    When the relevant set is empty, returns 1.0 (vacuously perfect recall — nothing
    to miss).

    Args:
        ranked: Ordered list of retrieved item IDs (most-relevant first).
        relevant: Set of ground-truth relevant item IDs.
        k: Number of top results to evaluate.

    Returns:
        Float in [0.0, 1.0].
    """
    if not relevant:
        return 1.0
    if not ranked:
        return 0.0
    top_k = ranked[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(relevant)


def mrr(ranked: list[str], relevant: set[str]) -> float:
    """Compute Mean Reciprocal Rank (MRR) for a single query.

    MRR equals 1/rank of the first relevant item in the ranked list.
    Returns 0.0 if no relevant item is found or if relevant is empty.

    Args:
        ranked: Ordered list of retrieved item IDs (most-relevant first).
        relevant: Set of ground-truth relevant item IDs.

    Returns:
        Float in [0.0, 1.0].
    """
    if not relevant or not ranked:
        return 0.0
    for rank, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0
