"""
Module: sequence_fidelity
Layer: evals (eval harness — not part of src/)
Purpose: Derive a SequenceRun's reset-fidelity tier from its repetitions' ResetReceipts
         (docs/SEQUENCE_STATS_POLICY.md §1-2), and build the fidelity-gated SequenceStat
         the runner hands to report formatters. This is the ISSUE-143 fix: the Wilson
         interval is withheld here, at the point the tier is known, so a PARTIAL run
         cannot re-acquire a confidence interval through a later formatting change —
         the formatter only ever sees what this module decided to compute.
         SequenceStat also carries `metrics_summary` (measurement-remediation Phase 3):
         the mean of each RepetitionRecord.metrics key across the repetitions that
         reported it. Unlike `interval`, this is never fidelity-gated — a mean is
         descriptive regardless of whether repetitions were independent; only the
         Wilson interval assumes i.i.d. Bernoulli trials.
Dependencies: pydantic, case_stats (evals/), rate_stats (evals/), reset_fidelity_record
              (evals/), sequence_records (evals/)
Used by: evals/sequence_runner.py (EVAL-P12.4), evals/sequence_rates.py
"""

from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field

from case_stats import Classification, classify
from rate_stats import pass_rate, wilson_interval
from reset_fidelity_record import FidelityTier, assign_tier
from sequence_records import ResetReceipt

# ---------------------------------------------------------------------------
# Fidelity derivation
# ---------------------------------------------------------------------------


def derive_fidelity(receipts: Sequence[ResetReceipt]) -> FidelityTier:
    """Derive a run's fidelity tier as the minimum tier across its receipts.

    Per SEQUENCE_STATS_POLICY.md §1: the fidelity of a SequenceRun is the minimum
    fidelity across all its Repetition records. One PARTIAL receipt (any
    ``surviving`` non-empty) demotes the entire run, even if every other
    repetition cleared cleanly.

    Args:
        receipts: One ResetReceipt per repetition, in execution order.
    Returns:
        'FULL' only if every receipt's `surviving` is empty; 'PARTIAL' otherwise.
    Raises:
        ValueError: When receipts is empty — a run's fidelity is undefined with
            no repetitions to derive it from.
    """
    if not receipts:
        raise ValueError("derive_fidelity requires at least one ResetReceipt")
    tiers = (assign_tier(receipt.surviving) for receipt in receipts)
    return "PARTIAL" if "PARTIAL" in tiers else "FULL"


# ---------------------------------------------------------------------------
# Fidelity-gated statistic
# ---------------------------------------------------------------------------


class SequenceStat(BaseModel):
    """Fidelity-gated pass-rate statistic for one scenario's k-repetition run.

    Replaces CaseStat for sequence reporting. `interval` is None whenever
    `fidelity` is PARTIAL, per SEQUENCE_STATS_POLICY.md §3 — the Wilson CI
    assumes i.i.d. Bernoulli trials, which a PARTIAL-fidelity run cannot
    guarantee. The report formatter renders exactly this object and has no
    access to the underlying receipts (SEQUENCE_STATS_POLICY.md §3's
    enforcement contract), so a PARTIAL run cannot re-acquire an interval
    through a formatting change downstream.

    Frozen to ensure immutability after construction.

    Attributes:
        scenario_id: Canonical scenario identifier.
        k: Number of repetitions the stat was computed over.
        passes: Count of repetitions where the scenario returned True.
        pass_rate: Raw fraction passes / k.
        fidelity: The run's reset-fidelity tier (minimum across all receipts).
        interval: Wilson 95% confidence interval, or None when fidelity is PARTIAL.
        classification: Stability verdict (stable_pass / flaky / stable_fail).
        surviving: State items observed surviving across the run's receipts (union,
            sorted). Descriptive only — never used to derive `interval`; that
            decision is already made by the time this field is populated.
        metrics_summary: Mean of each RepetitionRecord.metrics key across the
            repetitions that reported it (measurement-remediation Phase 3). Empty
            for every run whose repetitions carried no metrics — every promoted
            scenario today.
    """

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    k: int
    passes: int
    pass_rate: float
    fidelity: FidelityTier
    interval: tuple[float, float] | None
    classification: Classification
    surviving: tuple[str, ...]
    metrics_summary: dict[str, float] = Field(default_factory=dict)


def _mean_metrics(metrics: Sequence[dict[str, float]]) -> dict[str, float]:
    """Average each metric key across the repetitions that reported it.

    A key missing from some repetitions' dicts is averaged only over the
    repetitions that reported it — a probe metric that only applies under some
    post-drive state (e.g. a rate computed only when its denominator is nonzero)
    does not get silently zero-padded into a misleading mean.

    Args:
        metrics: One metrics dict per repetition, in execution order. Repetitions
            that reported no metrics contribute an empty dict.
    Returns:
        Mapping from metric key to its mean across the repetitions that reported it.
    """
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for rep_metrics in metrics:
        for key, value in rep_metrics.items():
            sums[key] = sums.get(key, 0.0) + value
            counts[key] = counts.get(key, 0) + 1
    return {key: total / counts[key] for key, total in sums.items()}


def sequence_stat(
    scenario_id: str,
    passes: int,
    receipts: Sequence[ResetReceipt],
    metrics: Sequence[dict[str, float]] = (),
) -> SequenceStat:
    """Build the fidelity-gated SequenceStat for one scenario's completed run.

    Args:
        scenario_id: Canonical scenario identifier.
        passes: Count of repetitions that returned True (0 <= passes <= len(receipts)).
        receipts: One ResetReceipt per repetition, in execution order. `k` is
            derived as `len(receipts)`.
        metrics: One metrics dict per repetition, aligned by index with `receipts`.
            Defaults to empty — every promoted scenario reports none.
    Returns:
        SequenceStat with `interval` populated only when every receipt was FULL,
        and `metrics_summary` holding the per-key mean across `metrics`.
    Raises:
        ValueError: When receipts is empty.
    """
    k = len(receipts)
    if k == 0:
        raise ValueError("sequence_stat requires at least one ResetReceipt")
    fidelity = derive_fidelity(receipts)
    interval = wilson_interval(passes, k) if fidelity == "FULL" else None
    surviving = tuple(sorted({item for r in receipts for item in r.surviving}))
    return SequenceStat(
        scenario_id=scenario_id,
        k=k,
        passes=passes,
        pass_rate=pass_rate(passes, k),
        fidelity=fidelity,
        interval=interval,
        classification=classify(passes, k),
        surviving=surviving,
        metrics_summary=_mean_metrics(metrics),
    )
