"""
Module: panel_metrics
Layer: evals (eval harness — not part of src/)
Purpose: Assemble every agreement statistic the judge panel publishes — Fleiss
         kappa with its CI, raw pairwise agreement, a per-criterion breakdown,
         and a repeat-flip decomposition separating engine variability from
         judge instability.
Dependencies: collections, dataclasses, typing; judge_panel (PanelScoredRecord,
         AgreementResult, pairwise_agreement), judged_persistence (apply_polarity),
         kappa_stats (KappaResult, fleiss_kappa, bootstrap_kappa_ci, rateable)
Used by: judge_runner (--panel), panel_metrics_format
Does NOT: call /v1/dialogue, read files, import from src/npc_engine/

WHY POLARITY IS APPLIED BEFORE ANY STATISTIC
Kappa is computed on pass/fail decisions, never on raw YES/NO scores. Pooling
raw scores across pass_on_yes and pass_on_no criteria artificially balances the
category marginals (pushing chance agreement toward 0.5) and inflates kappa —
on the 2026-08-17 data, from 0.53 to roughly 0.91. Agreement *rates* happen to
be invariant under polarity, because polarity is a bijection applied uniformly
to every seat on a record; kappa is not, because it depends on the marginals.

WHY GROUPING IS STRUCTURAL
Each PanelScoredRecord IS one rateable item (one record, one repetition), so
repetitions are never pooled and no pair ever compares a judge with itself.
The previous flat-verdict-list interface forced this grouping to be inferred
from record_id, which silently merged a k=3 run's three generations into one
9-vote item — 36 pairs where there should have been 9 (ISSUE-181).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from judge_panel import AgreementResult, PanelScoredRecord, pairwise_agreement
from judged_persistence import apply_polarity
from kappa_stats import KappaResult, bootstrap_kappa_ci, fleiss_kappa, rateable

# record_id is '<case>:<judge_kind>:<index>'; the case prefix is the bootstrap
# cluster, since a case's several criteria and k repeats are not independent.
_CASE_SEPARATOR: str = ":"


@dataclass(frozen=True)
class CriterionAgreement:
    """Agreement figures for one judge_kind in isolation.

    Attributes:
        judge_kind: The criterion these figures describe.
        n_items: Rateable items for this criterion.
        unanimous: Items where every available seat cast the same vote.
        kappa: Fleiss kappa within this criterion, or None when undefined.
    """

    judge_kind: str
    n_items: int
    unanimous: int
    kappa: float | None


@dataclass(frozen=True)
class RepeatFlipResult:
    """How often verdicts changed across the k regenerated responses per record.

    A flip is NOT pure judge instability: each repetition judged a *different*
    generated response, so a flip can be the engine varying rather than the judge
    wobbling. The decomposition is what separates them — when every seat flips
    together the engine moved; when one seat flips alone that seat is noisy.
    Together these bound the noise floor any A/B comparison must clear.

    Attributes:
        records_with_flips: record_ids where at least one seat changed verdict.
        unanimous_flips: record_ids where every seat flipped — engine-driven.
        solo_flips: record_ids where exactly one seat flipped — judge-driven.
        flips_by_judge: (judge_model, flip count) pairs, descending by count.
        n_records: record_ids that had more than one repetition to compare.
    """

    records_with_flips: int
    unanimous_flips: int
    solo_flips: int
    flips_by_judge: tuple[tuple[str, int], ...]
    n_records: int


@dataclass(frozen=True)
class PanelMetrics:
    """Everything the report publishes about panel agreement.

    Attributes:
        agreement: Raw pairwise agreement with its Wilson CI — kept as the
            secondary line because it is the number prior runs published.
        kappa: Chance-corrected agreement; the headline.
        by_criterion: Per-judge_kind breakdown, ordered by judge_kind.
        repeat_flips: Engine-vs-judge noise decomposition across repetitions.
        n_items: Rateable items overall.
        pass_base_rate: Fraction of all seat votes that were passes — the number
            that explains why raw agreement sits so far above kappa.
    """

    agreement: AgreementResult
    kappa: KappaResult
    by_criterion: tuple[CriterionAgreement, ...]
    repeat_flips: RepeatFlipResult
    n_items: int
    pass_base_rate: float


def _decisions(item: PanelScoredRecord) -> list[bool | None]:
    """Polarity-applied pass/fail decision per seat, preserving inconclusives."""
    polarity = item.record.expected_polarity
    return [
        None if v.score is None else apply_polarity(v.score, polarity)
        for v in item.verdicts
    ]


def _repeat_flips(scored: Sequence[PanelScoredRecord]) -> RepeatFlipResult:
    """Decompose verdict changes across repetitions into engine vs judge noise."""
    by_record: dict[str, dict[str, list[bool | None]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for item in scored:
        for verdict, decision in zip(item.verdicts, _decisions(item)):
            by_record[item.record.record_id][verdict.judge_model].append(decision)

    flips_by_judge: dict[str, int] = defaultdict(int)
    with_flips = unanimous = solo = comparable = 0
    for seats in by_record.values():
        multi = {m: votes for m, votes in seats.items() if len(votes) > 1}
        if not multi:
            continue
        comparable += 1
        flipped = [m for m, votes in multi.items() if len(set(votes)) > 1]
        for model in flipped:
            flips_by_judge[model] += 1
        if not flipped:
            continue
        with_flips += 1
        if len(flipped) == len(multi):
            unanimous += 1
        elif len(flipped) == 1:
            solo += 1

    return RepeatFlipResult(
        records_with_flips=with_flips,
        unanimous_flips=unanimous,
        solo_flips=solo,
        flips_by_judge=tuple(sorted(flips_by_judge.items(), key=lambda kv: (-kv[1], kv[0]))),
        n_records=comparable,
    )


def _by_criterion(scored: Sequence[PanelScoredRecord]) -> tuple[CriterionAgreement, ...]:
    """Compute per-judge_kind agreement figures."""
    grouped: dict[str, list[list[bool | None]]] = defaultdict(list)
    for item in scored:
        grouped[str(item.record.judge_kind)].append(_decisions(item))

    return tuple(
        CriterionAgreement(
            judge_kind=judge_kind,
            n_items=len(rateable(grouped[judge_kind])),
            unanimous=sum(1 for votes in rateable(grouped[judge_kind]) if len(set(votes)) == 1),
            kappa=fleiss_kappa(grouped[judge_kind]).kappa,
        )
        for judge_kind in sorted(grouped)
    )


def _with_interval(kappa: KappaResult, clusters: Sequence[Sequence[Sequence[bool | None]]]) -> KappaResult:
    """Attach a clustered bootstrap CI to a defined kappa; pass through otherwise."""
    if kappa.kappa is None:
        return kappa
    ci_low, ci_high = bootstrap_kappa_ci(clusters)
    return KappaResult(
        kappa=kappa.kappa,
        observed_agreement=kappa.observed_agreement,
        chance_agreement=kappa.chance_agreement,
        n_items=kappa.n_items,
        ci_low=ci_low,
        ci_high=ci_high,
    )


def compute_panel_metrics(scored: Sequence[PanelScoredRecord]) -> PanelMetrics:
    """Compute every published panel metric from per-record panel results.

    Args:
        scored: One PanelScoredRecord per judged record, across the transcript.
    Returns:
        PanelMetrics carrying kappa (headline), raw agreement, the per-criterion
        breakdown and the repeat-flip decomposition.
    """
    decisions = [_decisions(item) for item in scored]
    kept = rateable(decisions)

    clusters: dict[str, list[list[bool | None]]] = defaultdict(list)
    for item, votes in zip(scored, decisions):
        clusters[item.record.record_id.split(_CASE_SEPARATOR)[0]].append(votes)

    all_votes = [v for votes in kept for v in votes]
    base_rate = (sum(1 for v in all_votes if v) / len(all_votes)) if all_votes else 0.0

    return PanelMetrics(
        agreement=pairwise_agreement(decisions),
        kappa=_with_interval(fleiss_kappa(decisions), list(clusters.values())),
        by_criterion=_by_criterion(scored),
        repeat_flips=_repeat_flips(scored),
        n_items=len(kept),
        pass_base_rate=base_rate,
    )
