"""
Module: test_retrieval_eval
Layer: tests/unit
Purpose: Unit-test pure metric functions (precision@k, recall@k, MRR) in retrieval_matchers.
Dependencies: evals.retrieval_matchers
Used by: pytest
"""

from __future__ import annotations

import pytest

from evals.retrieval_matchers import mrr, precision_at_k, recall_at_k


# ---------------------------------------------------------------------------
# precision_at_k
# ---------------------------------------------------------------------------


def test_precision_at_k_basic():
    """2 out of 5 ranked results are relevant → 0.4."""
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c"}
    assert precision_at_k(ranked, relevant, k=5) == pytest.approx(0.4)


def test_precision_at_k_k_smaller_than_list():
    """Only first 2 results considered; 'a' is relevant → 0.5."""
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c"}
    assert precision_at_k(ranked, relevant, k=2) == pytest.approx(0.5)


def test_precision_at_k_all_relevant():
    """All 5 results are relevant → 1.0."""
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"a", "b", "c", "d", "e"}
    assert precision_at_k(ranked, relevant, k=5) == pytest.approx(1.0)


def test_precision_at_k_none_relevant():
    """No results are relevant → 0.0."""
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"x", "y"}
    assert precision_at_k(ranked, relevant, k=5) == pytest.approx(0.0)


def test_precision_at_k_empty_ranked():
    """Empty ranked list → 0.0."""
    assert precision_at_k([], {"a", "b"}, k=5) == pytest.approx(0.0)


def test_precision_at_k_empty_relevant():
    """Empty relevant set → 0.0."""
    ranked = ["a", "b", "c"]
    assert precision_at_k(ranked, set(), k=3) == pytest.approx(0.0)


def test_precision_at_k_k_larger_than_list():
    """k > len(ranked) — only available items counted; 1/3 relevant → 1/3."""
    ranked = ["a", "b", "c"]
    relevant = {"a"}
    assert precision_at_k(ranked, relevant, k=10) == pytest.approx(1 / 3)


def test_precision_at_k_k_zero():
    """k=0 edge case → 0.0 (no items evaluated)."""
    ranked = ["a", "b", "c"]
    relevant = {"a"}
    assert precision_at_k(ranked, relevant, k=0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# recall_at_k
# ---------------------------------------------------------------------------


def test_recall_at_k_basic():
    """Both relevant items appear in top-5 → 1.0."""
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c"}
    assert recall_at_k(ranked, relevant, k=5) == pytest.approx(1.0)


def test_recall_at_k_partial():
    """Only one of two relevant items in top-2 → 0.5."""
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c"}
    assert recall_at_k(ranked, relevant, k=2) == pytest.approx(0.5)


def test_recall_at_k_none_retrieved():
    """Relevant items are not in ranked list at all → 0.0."""
    ranked = ["a", "b", "c"]
    relevant = {"x", "y"}
    assert recall_at_k(ranked, relevant, k=3) == pytest.approx(0.0)


def test_recall_at_k_empty_relevant():
    """Empty relevant set: no items to recall → 1.0 (vacuously perfect recall)."""
    ranked = ["a", "b", "c"]
    assert recall_at_k(ranked, set(), k=3) == pytest.approx(1.0)


def test_recall_at_k_empty_ranked():
    """Empty ranked list with non-empty relevant → 0.0."""
    assert recall_at_k([], {"a", "b"}, k=5) == pytest.approx(0.0)


def test_recall_at_k_k_larger_than_list():
    """k > len(ranked) — only available items scanned; both relevant present → 1.0."""
    ranked = ["a", "b"]
    relevant = {"a", "b"}
    assert recall_at_k(ranked, relevant, k=10) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# mrr
# ---------------------------------------------------------------------------


def test_mrr_first_relevant_at_position_1():
    """First relevant item at rank 1 → MRR=1.0."""
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c"}
    assert mrr(ranked, relevant) == pytest.approx(1.0)


def test_mrr_first_relevant_at_position_2():
    """First relevant item at rank 2 → MRR=0.5."""
    ranked = ["b", "a", "c", "d", "e"]
    relevant = {"a"}
    assert mrr(ranked, relevant) == pytest.approx(0.5)


def test_mrr_first_relevant_at_position_3():
    """First relevant item at rank 3 → MRR=1/3."""
    ranked = ["b", "c", "a", "d", "e"]
    relevant = {"a"}
    assert mrr(ranked, relevant) == pytest.approx(1 / 3)


def test_mrr_no_relevant_found():
    """No relevant item in ranked list → MRR=0.0."""
    ranked = ["a", "b", "c"]
    relevant = {"x", "y"}
    assert mrr(ranked, relevant) == pytest.approx(0.0)


def test_mrr_empty_ranked():
    """Empty ranked list → MRR=0.0."""
    assert mrr([], {"a"}) == pytest.approx(0.0)


def test_mrr_empty_relevant():
    """Empty relevant set → MRR=0.0 (nothing to find)."""
    ranked = ["a", "b", "c"]
    assert mrr(ranked, set()) == pytest.approx(0.0)
