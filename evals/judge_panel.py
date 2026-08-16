"""
Module: judge_panel
Layer: evals (eval harness — not part of src/)
Purpose: Multi-judge panel execution and per-judge verdict persistence
         (EVAL-P21.1), plus the 2-of-3 consensus rule and inter-judge
         agreement metric (EVAL-P21.2). Closes ISSUE-129 fixes (1)-(3):
         published agreement, outvoted single-dissent false positives, and
         auditable per-judge verdicts.
Dependencies: dataclasses, typing; matchers (JudgeResult, _run_binary_judge),
              judge_config (DEFAULT_PANEL_MODELS), rate_stats (wilson_interval)
Used by: tests/unit/evals/test_judge_panel.py; judge_runner.py (live wiring —
         not yet connected; HUMAN GATE H7 stays closed until EVAL-P20.4
         actually runs, see ROADMAP.md EVAL-P21.1/P21.2 Notes, DEC-184)

SCAFFOLDING STATUS (2026-08-16): this module is real, tested code — not a
stub — but it is not wired into the live judge_runner.py pipeline. That
wiring is the actual EVAL-P21.1/P21.2 roadmap tasks, which stay genuinely
blocked by HUMAN GATE H7 until regeneration #1 (EVAL-P20.4) runs. See DEC-184.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from judge_config import DEFAULT_PANEL_MODELS
from matchers import JudgeResult, _run_binary_judge
from rate_stats import wilson_interval

# ISSUE-129 fix (2): a record only counts as a hallucination when at least
# this many of the panel's 3 seats vote fail — a single dissenting judge
# (the audit's case_neg_injection_001 false positive) must be outvoted.
_MIN_FAILURE_VOTES = 2


# ---------------------------------------------------------------------------
# Panel execution and persistence (EVAL-P21.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PanelVerdict:
    """One judge model's verdict for one record.

    Attributes:
        record_id: The scored record's stable id.
        judge_model: Which panel seat produced this verdict.
        score: True (fail/YES) / False (pass/NO) / None (infra failure —
            inconclusive, never a silent pass).
        error: Reasoning text (score=False) or 'infra_failure' (score=None).
    """

    record_id: str
    judge_model: str
    score: bool | None
    error: str


def _default_judge_fn(model: str, criteria: str, content: str) -> JudgeResult:
    """Call the shared binary-judge transport for one panel seat."""
    return _run_binary_judge(criteria, content, model=model)


def run_panel(
    record_id: str,
    criteria: str,
    content: str,
    *,
    models: Sequence[str] = DEFAULT_PANEL_MODELS,
    judge_fn: Callable[[str, str, str], JudgeResult] = _default_judge_fn,
) -> list[PanelVerdict]:
    """Run one record's (criteria, content) through every panel seat.

    Args:
        record_id: The record being judged.
        criteria: The YES/NO criterion embedded in the judge prompt.
        content: The text being judged (the NPC response).
        models: Panel roster to query; defaults to judge_config.DEFAULT_PANEL_MODELS.
        judge_fn: Callable(model, criteria, content) -> JudgeResult; injectable
            for testing without a live Ollama panel.
    Returns:
        One PanelVerdict per model, in roster order.
    """
    return [
        PanelVerdict(
            record_id=record_id,
            judge_model=model,
            score=result.score,
            error=result.error,
        )
        for model in models
        for result in [judge_fn(model, criteria, content)]
    ]


def to_judged_rows(verdicts: Sequence[PanelVerdict]) -> list[dict]:
    """Convert PanelVerdicts into judged.jsonl-shaped rows, one per judge per record.

    An inconclusive verdict (score=None) is written with passed=False and
    inconclusive=True — never a silent pass (mirrors summary.py's existing
    inconclusive-vs-content-failure convention, EVAL-P17.3).

    Args:
        verdicts: PanelVerdict list from run_panel.
    Returns:
        List of row dicts: record_id, judge_model, score, passed, inconclusive, error.
    """
    return [
        {
            "record_id": v.record_id,
            "judge_model": v.judge_model,
            "score": v.score,
            "passed": bool(v.score),
            "inconclusive": v.score is None,
            "error": v.error,
        }
        for v in verdicts
    ]


# ---------------------------------------------------------------------------
# Consensus rule and inter-judge agreement (EVAL-P21.2)
# ---------------------------------------------------------------------------


def consensus_verdict(votes: Sequence[bool | None]) -> tuple[bool, int]:
    """Apply the ≥2-of-3 consensus rule to a set of per-judge votes.

    A record counts as a confirmed failure/hallucination only when at least
    _MIN_FAILURE_VOTES of the panel's votes are True. An inconclusive (None)
    vote never itself counts toward that threshold — it simply is not True.

    Args:
        votes: Per-judge score values (True=fail, False=pass, None=inconclusive).
    Returns:
        (consensus, n_available) — consensus is True only when the failure
        votes reach the threshold; n_available is the count of non-None votes,
        for reporting how much of the panel actually weighed in.
    """
    n_available = sum(1 for v in votes if v is not None)
    n_failures = sum(1 for v in votes if v is True)
    return (n_failures >= _MIN_FAILURE_VOTES, n_available)


@dataclass(frozen=True)
class AgreementResult:
    """Pairwise inter-judge agreement rate with a Wilson CI.

    Scope note (DEC-184): implemented as pairwise agreement (fraction of
    judge-pairs, across all records, that cast the same vote), not Fleiss'
    kappa — Fleiss' kappa additionally corrects for chance agreement given
    each category's base rate, which needs the live panel's actual vote
    distribution to compute meaningfully. Pairwise agreement is the simpler,
    already-available metric; revisit with Fleiss' kappa once EVAL-P21.1's
    live run produces real vote data to correct against.

    Attributes:
        agreeing_pairs: Judge-pairs (across all records) that cast the same vote.
        total_pairs: All judge-pairs with both votes available (non-None).
        rate: agreeing_pairs / total_pairs; None when total_pairs == 0.
        ci_low: Lower bound of the 95% Wilson CI; None when total_pairs == 0.
        ci_high: Upper bound of the 95% Wilson CI; None when total_pairs == 0.
    """

    agreeing_pairs: int
    total_pairs: int
    rate: float | None
    ci_low: float | None
    ci_high: float | None


def pairwise_agreement(records: Sequence[Sequence[bool | None]]) -> AgreementResult:
    """Compute pairwise inter-judge agreement across a set of judged records.

    Each record contributes one pair-comparison per pair of judges that both
    returned a non-None vote — a record with fewer than 2 real votes
    contributes no pairs (an inconclusive judge cannot be compared against).

    Args:
        records: One sequence of per-judge votes per record (True/False/None).
    Returns:
        AgreementResult with the pairwise rate and its Wilson CI.
    """
    agreeing = 0
    total = 0
    for votes in records:
        available = [v for v in votes if v is not None]
        for i in range(len(available)):
            for j in range(i + 1, len(available)):
                total += 1
                if available[i] == available[j]:
                    agreeing += 1

    if total == 0:
        return AgreementResult(agreeing_pairs=0, total_pairs=0, rate=None, ci_low=None, ci_high=None)

    rate = agreeing / total
    ci_low, ci_high = wilson_interval(agreeing, total)
    return AgreementResult(
        agreeing_pairs=agreeing, total_pairs=total, rate=rate, ci_low=ci_low, ci_high=ci_high
    )
