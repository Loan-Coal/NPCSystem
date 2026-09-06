"""
Module: label_export_sampling
Layer: evals (eval harness — not part of src/)
Purpose: Seeded, deterministic selection of a stratified label-export batch —
         every unlabelled expected-negative candidate for a scorer, plus a
         seeded sample of unlabelled expected-positive candidates capped at the
         negative count, so the batch oversamples the minority-eliciting stratum
         without excluding the majority stratum outright (this task, 2026-09-04).
         Distinct from evals/label_sampling.py, which orders an already-judged
         corpus for labelling priority; this module selects WHICH unlabelled
         candidates enter a not-yet-labelled batch in the first place.
Dependencies: random, typing; export_item (ExportItem), label_export_strata
         (case_id_of, stratum_of)
Used by: label_export_stratified (CLI batch construction),
         tests/unit/evals/test_label_export_sampling.py
"""

from __future__ import annotations

import random
from typing import Sequence

from export_item import ExportItem
from label_export_strata import case_id_of, stratum_of

LabelKey = tuple[str, str]


def select_stratified_batch(
    scorer: str,
    candidate_items: Sequence[ExportItem],
    already_labelled_keys: frozenset[LabelKey],
    negative_cases: frozenset[str],
    *,
    seed: int,
) -> list[ExportItem]:
    """Select an oversampled, seeded-shuffled batch for one scorer.

    Every unlabelled expected-negative candidate is included (they are the rare,
    high-signal stratum). Unlabelled expected-positive candidates are sampled,
    seeded, down to the negative count (or kept whole if there are fewer than
    that many) — oversampling relative to the corpus's natural ~94/6 split
    without dropping the majority stratum from the batch entirely.

    Args:
        scorer: Scorer identifier to build the batch for.
        candidate_items: Every ExportItem built from the candidate transcript,
            any scorer — filtered to `scorer` internally.
        already_labelled_keys: (record_id, scorer) keys that already carry a
            label — excluded so the batch never re-asks for an existing verdict.
        negative_cases: Declared expected-negative case_ids (label_export_strata).
        seed: RNG seed — same inputs + seed always produce the same batch and order.
    Returns:
        The batch items, shuffled under `seed`. Length is
        len(negative) + min(len(negative), len(positive)), or just len(positive)
        when there are no negative candidates at all.
    """
    pool = _unlabelled_pool(scorer, candidate_items, already_labelled_keys)
    negative, positive = _split_by_stratum(pool, negative_cases)

    rng = random.Random(seed)
    rng.shuffle(positive)
    sampled_positive = positive[: len(negative)] if negative else positive

    combined = negative + sampled_positive
    rng.shuffle(combined)
    return combined


def _unlabelled_pool(
    scorer: str,
    candidate_items: Sequence[ExportItem],
    already_labelled_keys: frozenset[LabelKey],
) -> list[ExportItem]:
    """This scorer's candidate items that do not already carry a label.

    Split out of select_stratified_batch purely to keep that function under
    the 40-line cap.
    """
    return [
        item
        for item in candidate_items
        if item.scorer == scorer and (item.record_id, item.scorer) not in already_labelled_keys
    ]


def _split_by_stratum(
    items: Sequence[ExportItem],
    negative_cases: frozenset[str],
) -> tuple[list[ExportItem], list[ExportItem]]:
    """Split items into (expected_negative, expected_positive) lists, order preserved."""
    negative: list[ExportItem] = []
    positive: list[ExportItem] = []
    for item in items:
        bucket = negative if stratum_of(case_id_of(item.record_id), negative_cases) == "expected_negative" else positive
        bucket.append(item)
    return negative, positive
