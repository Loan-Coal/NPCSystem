"""
Module: comparability
Layer: evals (eval harness — not part of src/)
Purpose: The policy for whether two runs' numbers may be compared at all. One
         module owns it so the trend gate and compare.py cannot drift apart on the
         question — they already did once, which is DEC-197.
Dependencies: pydantic; trend_store (TrendRow, TYPE_CHECKING only — the predicate
         reads attributes at runtime, so the import stays type-level and no cycle
         forms with trend_store, which imports this module for real)
Used by: trend_store (latest_comparable_row), baseline_selection (the walk-back and
         its refusal messages), scripts/record_trend_and_gate.py
Does NOT: read files, choose a baseline, or decide whether anything regressed.

WHY THIS IS A SEPARATE MODULE
It was inline in trend_store.py until adding the judge dimension pushed that file to
312 lines, past the 300-line cap. The split is the honest boundary anyway: storage
is "what rows exist", comparability is "which of them may be spoken about together",
and the second is a policy that two other modules need to apply identically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from trend_store import TrendRow


class ComparabilityKey(BaseModel):
    """Everything two runs must share before their numbers may be compared.

    Two dimensions, both load-bearing and for different reasons:

    - `harness_version` hashes evals/cases/, prompts/eval/ and matchers.py, so a
      case or judge-criterion edit changes what is being measured.
    - `judge_identity` is the instrument that actually scored the run. compare.py
      has refused cross-instrument pairs since DEC-190, but the trend gate — which
      Run-EvalHarness.ps1 declares AUTHORITATIVE over compare — checked only the
      first dimension until DEC-197. A panel-scored baseline gating a single-judge
      candidate puts the instrument change inside the delta and reports it as an
      engine verdict, which is the confound DEC-190 exists to prevent.

    Deliberately NOT included: retrieval_profile, git_sha, dialogue_prompt_hash.
    Those are the independent variable — the thing an A/B is varying on purpose —
    and refusing on them would refuse every comparison worth making (DEC-194).

    Attributes:
        harness_version: The candidate run's harness_version.
        judge_identity: The candidate run's resolved judge identity. Empty means
            unknown, and an unknown instrument matches nothing.
    """

    model_config = ConfigDict(frozen=True)

    harness_version: str
    judge_identity: str


def key_for(row: TrendRow) -> ComparabilityKey:
    """Build the comparability key a row would be gated against.

    Args:
        row: The candidate run's trend row.
    Returns:
        The key carrying that row's own two comparability dimensions, so a
        candidate and the baseline it selects cannot disagree about what
        "comparable" meant.
    """
    return ComparabilityKey(
        harness_version=row.harness_version, judge_identity=row.judge_identity
    )


def is_comparable(row: TrendRow, key: ComparabilityKey) -> bool:
    """Whether `row`'s numbers may be compared against a run described by `key`.

    Args:
        row: A stored trend row.
        key: The candidate run's comparability key.
    Returns:
        True only when both dimensions match AND the judge identity is known on
        both sides. An empty judge_identity is refused rather than treated as a
        wildcard: the store is empty as of DEC-197, so strictness costs nothing
        now and stops an instrument-unknown row from silently serving as a
        baseline later.
    """
    if not key.judge_identity or not row.judge_identity:
        return False
    # bool(...): pydantic field access resolves as Any to mypy (no-any-return
    # otherwise), the same gap regression_gate._rate_regressed documents. The
    # comparison already yields a genuine bool.
    return bool(
        row.harness_version == key.harness_version
        and row.judge_identity == key.judge_identity
    )
