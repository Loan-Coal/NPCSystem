"""
Tests for the RetrievalSummary dataclass and its helper functions in evals.summary.

All tests are pure unit tests — no I/O, no Neo4j, no network.
"""

from __future__ import annotations

from evals.retrieval_summary import (
    PRECISION_THRESHOLD,
    RetrievalSummary,
    format_retrieval_summary_lines,
    format_retrieval_summary_markdown,
    summarize_retrieval,
)


def test_summarize_retrieval_computes_means():
    results = [
        {"p_at_k": 1.0, "r_at_k": 0.8, "mrr_score": 1.0},
        {"p_at_k": 0.5, "r_at_k": 0.5, "mrr_score": 0.5},
        {"p_at_k": 0.0, "r_at_k": 0.0, "mrr_score": 0.0},
    ]
    s = summarize_retrieval(results)
    assert abs(s.mean_precision_at_k - 0.5) < 1e-9
    assert abs(s.mean_recall_at_k - (1.3 / 3)) < 1e-9
    assert abs(s.mean_mrr - 0.5) < 1e-9
    assert s.total_cases == 3


def test_summarize_retrieval_counts_above_threshold():
    results = [
        {"p_at_k": 1.0, "r_at_k": 1.0, "mrr_score": 1.0},
        {"p_at_k": 0.5, "r_at_k": 0.5, "mrr_score": 0.5},  # == threshold → counts
        {"p_at_k": 0.3, "r_at_k": 0.3, "mrr_score": 0.3},
    ]
    s = summarize_retrieval(results)
    assert s.cases_above_threshold == 2


def test_summarize_retrieval_empty_list():
    s = summarize_retrieval([])
    assert s.total_cases == 0
    assert s.mean_precision_at_k == 0.0
    assert s.mean_recall_at_k == 0.0
    assert s.mean_mrr == 0.0
    assert s.cases_above_threshold == 0


def test_summarize_retrieval_headline_format():
    s = summarize_retrieval([{"p_at_k": 0.8, "r_at_k": 0.7, "mrr_score": 0.9}])
    assert "Retrieval P@k:" in s.headline


def test_format_retrieval_summary_lines_contains_headline():
    s = summarize_retrieval([{"p_at_k": 0.8, "r_at_k": 0.7, "mrr_score": 0.9}])
    lines = format_retrieval_summary_lines(s)
    assert any("Retrieval P@k:" in line for line in lines)


def test_format_retrieval_summary_markdown_contains_table():
    s = summarize_retrieval([{"p_at_k": 0.8, "r_at_k": 0.7, "mrr_score": 0.9}])
    lines = format_retrieval_summary_markdown(s)
    assert any(line.startswith("|") for line in lines)
