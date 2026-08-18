"""
Module: panel_metric_records
Layer: evals (eval harness — not part of src/)
Purpose: The persisted shape of the judge panel's agreement statistics — kappa
         with its bootstrap interval, the per-criterion breakdown, and the
         repeat-flip decomposition. One module owns these models so that
         `run_status.json` (what a judge pass measured) and `trend_v1.jsonl`
         (what the trend records) cannot drift apart the way `judged.jsonl`'s
         two writers did (DEC-187).
Dependencies: pydantic
Used by: run_status (writes them into run_status.json), trend_store (TrendRow),
         judge_run_artifacts (maps panel_metrics.PanelMetrics onto them),
         instrument_gate (reads PanelKappa)
Does NOT: compute any statistic — panel_metrics.py owns the arithmetic; this
         module is the wire format only, so it stays import-light and can be
         read by both a status writer and a trend reader without a cycle.

WHY THE TREND RECORDS KAPPA AND NOT RAW AGREEMENT (DEC-188)
On the 2026-08-17 corpus raw pairwise agreement reads 0.956 while Fleiss kappa
reads 0.526, because 95.1% of records pass and two rubber-stamping judges would
have agreed 0.906 by luck. A trend built on the raw number tracks base rate as
much as it tracks the instrument. `panel_agreement_rate` stays on TrendRow for
continuity with already-written rows; these models carry the honest figures.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PanelKappa(BaseModel):
    """Overall Fleiss kappa for a panel run, with its clustered bootstrap CI.

    Attributes:
        kappa: Chance-corrected agreement; None when undefined (an
            all-one-category corpus has no variance to correct for, and is
            reported as undefined rather than as 1.0).
        ci_low: Lower bound of the seeded cluster-bootstrap 95% CI, when computed.
        ci_high: Upper bound of that CI, when computed. The gate compares this
            against the baseline's point estimate; without it no instrument
            check can run at all.
        n_items: Rateable items the kappa was computed over.
    """

    model_config = ConfigDict(frozen=True)

    kappa: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    n_items: int = 0


class CriterionKappa(BaseModel):
    """One judge_kind's agreement in isolation.

    Carries no interval on purpose: `panel_metrics.CriterionAgreement` computes
    none, and inventing a point-estimate comparison per criterion would
    reintroduce exactly the noise-driven gate DEC-185 records. These numbers
    localise a drop for a human; the gate fires on the overall kappa.

    Attributes:
        judge_kind: The criterion these figures describe.
        kappa: Fleiss kappa within this criterion, or None when undefined.
        n_items: Rateable items for this criterion.
        unanimous: Items where every available seat cast the same vote.
    """

    model_config = ConfigDict(frozen=True)

    judge_kind: str
    kappa: float | None = None
    n_items: int = 0
    unanimous: int = 0


class RepeatFlips(BaseModel):
    """Verdict changes across the k regenerated responses per record.

    A flip is not pure judge instability — each repetition judged a *different*
    generated response. Unanimous flips are the engine varying; solo flips are
    one seat wobbling. Together they bound the noise floor any A/B effect must
    clear, which is why the trend keeps them rather than only kappa.

    Attributes:
        records_with_flips: record_ids where at least one seat changed verdict.
        unanimous_flips: record_ids where every seat flipped — engine-driven.
        solo_flips: record_ids where exactly one seat flipped — judge-driven.
        n_records: record_ids that had more than one repetition to compare.
    """

    model_config = ConfigDict(frozen=True)

    records_with_flips: int = 0
    unanimous_flips: int = 0
    solo_flips: int = 0
    n_records: int = 0
