"""
Module: label_sampling
Layer: evals (eval harness — not part of src/)
Purpose: Deterministic, seeded ordering of labelling items, stratified by
         (scorer, verdict), so the rarest and highest-signal rows are
         adjudicated first instead of being buried behind hundreds of
         same-verdict passes. Rescoped from EVAL-P22.1's original ~150-row
         stratified SAMPLE (a cost-driven cap written when labelling meant
         hours of human time) to a full-corpus BATCHING/ORDERING utility —
         every row still gets labelled; this only decides the order and
         names which (scorer, verdict) combinations have zero rows to
         label at all, so that gap is explicit rather than discovered by
         someone re-deriving it later. See project-harness/DECISIONS.md
         (EVAL-P22.1 rescope) and ROADMAP.md Phase A5.
Dependencies: dataclasses, random, typing (stdlib only — no evals/ imports,
         so it stays reusable from either the record-level export path or
         a plain (key, scorer, verdict) triple built ad hoc)
Used by: tests/unit/evals/test_label_sampling.py; Phase C's full-corpus
         batch export (project-harness/ROADMAP.md)
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

# A labelling item, identified by any caller-chosen key (e.g. a composite
# record_id) paired with the scorer it was judged by and the scorer's own
# verdict on it — the stratification axis this module orders by.
LabelRow = tuple[str, str, bool]


@dataclass(frozen=True)
class Stratum:
    """All labelling keys sharing one (scorer, verdict) combination.

    Attributes:
        scorer: The scorer name (e.g. 'keyword_none', 'tone_judge').
        verdict: The scorer's own verdict for every key in this stratum.
        keys: The labelling keys, in stable input order (pre-shuffle).
    """

    scorer: str
    verdict: bool
    keys: tuple[str, ...]


def stratify(rows: Sequence[LabelRow]) -> list[Stratum]:
    """Group rows into (scorer, verdict) strata, ordered rarest-first.

    Ties in stratum size break on (scorer, verdict) for determinism — the
    ordering never depends on dict iteration order or input order alone.

    Args:
        rows: (key, scorer, verdict) triples, any order, duplicates allowed
            (a caller passing the same key twice gets it counted twice —
            deduplication is the caller's responsibility, since a key can
            legitimately appear once per scorer it was judged by).
    Returns:
        Strata sorted by ascending size, then by (scorer, verdict).
    """
    grouped: dict[tuple[str, bool], list[str]] = {}
    for key, scorer, verdict in rows:
        grouped.setdefault((scorer, verdict), []).append(key)

    strata = [
        Stratum(scorer=scorer, verdict=verdict, keys=tuple(keys))
        for (scorer, verdict), keys in grouped.items()
    ]
    strata.sort(key=lambda s: (len(s.keys), s.scorer, s.verdict))
    return strata


def order_for_labelling(rows: Sequence[LabelRow], *, seed: int) -> list[str]:
    """Deterministically order labelling keys, rarest stratum first.

    Strata are visited smallest-first (see stratify), each stratum's keys
    are seeded-shuffled for a reproducible-but-non-alphabetic internal
    order, then all strata are round-robin interleaved so labelling starts
    surfacing the least-represented (scorer, verdict) combinations
    immediately rather than exhausting the largest stratum first.

    Args:
        rows: (key, scorer, verdict) triples.
        seed: RNG seed — same rows + seed always produce the same order.
    Returns:
        Labelling keys in priority order. Length equals len(rows); a key
        appearing under two different scorers appears twice, once per
        (scorer, verdict) pair it belongs to.
    """
    strata = stratify(rows)
    rng = random.Random(seed)
    shuffled: list[list[str]] = []
    for stratum in strata:
        keys = list(stratum.keys)
        rng.shuffle(keys)
        shuffled.append(keys)

    ordered: list[str] = []
    index = 0
    while any(index < len(bucket) for bucket in shuffled):
        for bucket in shuffled:
            if index < len(bucket):
                ordered.append(bucket[index])
        index += 1
    return ordered


def coverage_report(rows: Sequence[LabelRow]) -> list[str]:
    """Name every scorer with zero rows of one verdict — an unmeasurable stratum.

    A scorer whose corpus never produced a False (or never produced a True)
    verdict cannot have its accuracy on that class measured no matter how
    thoroughly the present rows are labelled — that gap belongs in the
    labelling pass's own report, not discovered later when someone asks why
    a scorer's recall was never quoted (see the measured keyword_none
    finding: 207 rows, 0 failures, in evals/generations/k3_73e6c36).

    Args:
        rows: (key, scorer, verdict) triples.
    Returns:
        One line per (scorer, missing verdict), sorted by scorer name.
        Empty when every scorer present has at least one row of both
        verdicts.
    """
    verdicts_by_scorer: dict[str, set[bool]] = {}
    for _key, scorer, verdict in rows:
        verdicts_by_scorer.setdefault(scorer, set()).add(verdict)

    gaps: list[str] = []
    for scorer in sorted(verdicts_by_scorer):
        seen = verdicts_by_scorer[scorer]
        for verdict in (True, False):
            if verdict not in seen:
                gaps.append(f"{scorer}: zero rows with verdict={verdict}")
    return gaps
