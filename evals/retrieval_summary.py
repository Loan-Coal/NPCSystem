"""
Module: retrieval_summary
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Compute the retrieval-quality headline metric (P@k / R@k / MRR roll-up)
         from a completed retrieval eval run. Pure Python — no I/O, no network.
Dependencies: stdlib only (dataclasses).
Used by: retrieval_runner.py (console output), report.py (markdown summary section).
"""

from __future__ import annotations

from dataclasses import dataclass

_SEPARATOR: str = "=" * 60

PRECISION_THRESHOLD: float = 0.5


@dataclass(frozen=True)
class RetrievalSummary:
    """Immutable roll-up of one retrieval eval run.

    Attributes:
        total_cases: Number of labeled retrieval cases evaluated.
        mean_precision_at_k: Average P@k across all cases.
        mean_recall_at_k: Average R@k across all cases.
        mean_mrr: Average MRR across all cases.
        cases_above_threshold: Cases where P@k >= PRECISION_THRESHOLD.
    """

    total_cases: int
    mean_precision_at_k: float
    mean_recall_at_k: float
    mean_mrr: float
    cases_above_threshold: int

    @property
    def headline(self) -> str:
        """Single-line summary: 'Retrieval P@k: 0.85 (17/20 cases >= 0.50)'."""
        return (
            f"Retrieval P@k: {self.mean_precision_at_k:.2f} "
            f"({self.cases_above_threshold}/{self.total_cases} cases >= {PRECISION_THRESHOLD:.2f})"
        )


def summarize_retrieval(results: list[dict]) -> RetrievalSummary:
    """Compute RetrievalSummary from run_eval() output dicts.

    Args:
        results: List of dicts with keys p_at_k, r_at_k, mrr_score.
    Returns:
        Zeroed RetrievalSummary when results is empty.
    """
    if not results:
        return RetrievalSummary(
            total_cases=0,
            mean_precision_at_k=0.0,
            mean_recall_at_k=0.0,
            mean_mrr=0.0,
            cases_above_threshold=0,
        )
    n = len(results)
    mean_p = sum(r["p_at_k"] for r in results) / n
    mean_r = sum(r["r_at_k"] for r in results) / n
    mean_mrr_val = sum(r["mrr_score"] for r in results) / n
    above = sum(1 for r in results if r["p_at_k"] >= PRECISION_THRESHOLD)
    return RetrievalSummary(
        total_cases=n,
        mean_precision_at_k=mean_p,
        mean_recall_at_k=mean_r,
        mean_mrr=mean_mrr_val,
        cases_above_threshold=above,
    )


def format_retrieval_summary_lines(summary: RetrievalSummary) -> list[str]:
    """Render retrieval summary as plain-text console lines.

    Matches the visual style of summary.format_summary_lines().
    """
    return [
        _SEPARATOR,
        "RETRIEVAL QUALITY",
        _SEPARATOR,
        f"  {summary.headline}",
        "",
        f"  Mean Precision@k : {summary.mean_precision_at_k:.3f}",
        f"  Mean Recall@k    : {summary.mean_recall_at_k:.3f}",
        f"  Mean MRR         : {summary.mean_mrr:.3f}",
        f"  Total cases      : {summary.total_cases}",
        _SEPARATOR,
    ]


def format_retrieval_summary_markdown(summary: RetrievalSummary) -> list[str]:
    """Render retrieval summary as markdown lines.

    Matches the style of summary.format_summary_markdown().
    """
    return [
        "## Retrieval Quality",
        "",
        f"**{summary.headline}**",
        "",
        "| Metric | Score |",
        "|---|---|",
        f"| Mean Precision@k | {summary.mean_precision_at_k:.3f} |",
        f"| Mean Recall@k | {summary.mean_recall_at_k:.3f} |",
        f"| Mean MRR | {summary.mean_mrr:.3f} |",
        f"| Cases above threshold | {summary.cases_above_threshold} / {summary.total_cases} |",
        "",
        "---",
        "",
    ]
