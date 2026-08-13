"""
Module: sequence_fidelity
Layer: evals (eval harness — not part of src/)
Purpose: Derive a SequenceRun's reset-fidelity tier from its repetitions' ResetReceipts
         (docs/SEQUENCE_STATS_POLICY.md §1-2), and build the fidelity-gated SequenceStat
         the runner hands to report formatters. This is the ISSUE-143 fix: the Wilson
         interval is withheld here, at the point the tier is known, so a PARTIAL run
         cannot re-acquire a confidence interval through a later formatting change —
         the formatter only ever sees what this module decided to compute.
Dependencies: pydantic, case_stats (evals/), rate_stats (evals/), reset_fidelity_record
              (evals/), sequence_records (evals/)
Used by: evals/sequence_runner.py (EVAL-P12.4), evals/sequence_rates.py
"""

from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, ConfigDict

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


def sequence_stat(
    scenario_id: str,
    passes: int,
    receipts: Sequence[ResetReceipt],
) -> SequenceStat:
    """Build the fidelity-gated SequenceStat for one scenario's completed run.

    Args:
        scenario_id: Canonical scenario identifier.
        passes: Count of repetitions that returned True (0 <= passes <= len(receipts)).
        receipts: One ResetReceipt per repetition, in execution order. `k` is
            derived as `len(receipts)`.
    Returns:
        SequenceStat with `interval` populated only when every receipt was FULL.
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
    )
