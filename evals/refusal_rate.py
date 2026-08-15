"""
Module: refusal_rate
Layer: evals (eval harness — not part of src/)
Purpose: Score grounded NPC responses for over-refusal — detecting when an NPC
         refuses to share knowledge it holds in the knowledge graph. Reports the
         over-refusal rate with Wilson CI for display alongside guard/capability rates.
Dependencies: matchers (judge_refusal, JudgeResult), rate_stats (pass_rate, wilson_interval)
Used by: tests/unit/evals/test_refusal_rate.py; summary.format_summary_lines /
         summary.format_summary_markdown (EVAL-P20.3)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from matchers import JudgeResult, judge_refusal
from rate_stats import pass_rate, wilson_interval

# Format string matching the guard/capability rate display in summary.py, extended
# with the excluded (infra-failure) count so a run where most of the battery got no
# verdict cannot silently read as a clean "2/10".
_RATE_FMT: str = (
    "{k}/{n}  {rate:.3f}  95% CI [{ci_low:.3f}–{ci_high:.3f}]"
    "  (excluded: {excluded}/{total})"
)
_NO_DATA: str = "N/A (no evaluated turns)"
_NO_DATA_WITH_EXCLUDED_FMT: str = (
    "N/A (no evaluated turns; excluded: {excluded}/{total} — infra failures)"
)


@dataclass(frozen=True)
class RefusalRateResult:
    """Over-refusal rate for a set of grounded NPC responses.

    An over-refusal is when the NPC refuses to share knowledge it holds in the
    graph, on a grounded (positively-knowledge-anchored) question. The denominator
    excludes infra failures (score=None) to avoid silently diluting the rate.

    Attributes:
        total_grounded: Total grounded responses passed to the scorer.
        evaluated: Cases with a definite verdict (True or False; excludes None).
        over_refusals: Cases where the judge said YES (NPC refused a grounded question).
        rate: over_refusals / evaluated; None when evaluated == 0.
        ci_low: Lower Wilson CI bound; None when evaluated == 0.
        ci_high: Upper Wilson CI bound; None when evaluated == 0.
    """

    total_grounded: int
    evaluated: int
    over_refusals: int
    rate: float | None
    ci_low: float | None
    ci_high: float | None


def score_refusal_rate(
    npc_responses: Sequence[str],
    *,
    judge_fn: Callable[[str], JudgeResult] = judge_refusal,
) -> RefusalRateResult:
    """Score grounded NPC responses for over-refusal.

    Calls judge_fn for each response. Infra failures (score=None) are excluded
    from the denominator. A YES verdict (score=True) means the NPC refused — that
    is an over-refusal failure for a grounded case.

    Args:
        npc_responses: NPC response texts to score.
        judge_fn: Callable matching judge_refusal's signature; injectable for testing.
    Returns:
        RefusalRateResult with counts and Wilson CI.
    """
    total = len(npc_responses)
    evaluated = 0
    over_refusals = 0

    for response in npc_responses:
        verdict: JudgeResult = judge_fn(response)
        if verdict.score is None:
            continue  # infra failure — exclude from denominator
        evaluated += 1
        if verdict.score:  # YES = NPC refused = over-refusal
            over_refusals += 1

    if evaluated == 0:
        return RefusalRateResult(
            total_grounded=total,
            evaluated=evaluated,
            over_refusals=over_refusals,
            rate=None,
            ci_low=None,
            ci_high=None,
        )

    rate = pass_rate(over_refusals, evaluated)
    ci_low, ci_high = wilson_interval(over_refusals, evaluated)
    return RefusalRateResult(
        total_grounded=total,
        evaluated=evaluated,
        over_refusals=over_refusals,
        rate=rate,
        ci_low=ci_low,
        ci_high=ci_high,
    )


def fmt_refusal_rate(result: RefusalRateResult) -> str:
    """Format the over-refusal rate as a compact string for report display.

    Format matches the guard/capability rate lines in summary.py, plus an explicit
    excluded (infra-failure) count — without it, a run where most of the battery
    got no verdict (e.g. Ollama timeouts) would print a clean-looking 'k/n' that
    hides how much of the battery was actually silently dropped.

    Args:
        result: RefusalRateResult from score_refusal_rate.
    Returns:
        Formatted rate string, or an 'N/A' notice when rate is None.
    """
    excluded = result.total_grounded - result.evaluated
    if result.rate is None:
        if result.total_grounded == 0:
            return _NO_DATA
        return _NO_DATA_WITH_EXCLUDED_FMT.format(
            excluded=excluded, total=result.total_grounded
        )
    return _RATE_FMT.format(
        k=result.over_refusals,
        n=result.evaluated,
        rate=result.rate,
        ci_low=result.ci_low,
        ci_high=result.ci_high,
        excluded=excluded,
        total=result.total_grounded,
    )
