"""
Module: test_label_export_sampling
Layer: test (unit)
Purpose: Unit tests for label_export_sampling.py — seeded selection of a
         stratified label-export batch (every unlabelled expected-negative
         candidate, plus a seeded, capped sample of expected-positive ones).
Dependencies: pytest; export_item, label_export_sampling (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from export_item import ExportItem
from label_export_sampling import select_stratified_batch


def _item(record_id: str, scorer: str = "commits_judge") -> ExportItem:
    return ExportItem(
        record_id=record_id,
        scorer=scorer,
        npc_id="npc_a",
        player_message="hi",
        criteria="answer yes",
        output_text="an answer",
    )


def test_every_negative_candidate_is_included() -> None:
    """The rare stratum is never dropped, however many positive candidates exist."""
    negative_cases = frozenset({"case_neg_a", "case_neg_b"})
    items = [
        _item("case_neg_a:commits_judge:0#r0"),
        _item("case_neg_b:commits_judge:0#r0"),
    ] + [_item(f"case_pos_{i:03d}:commits_judge:0#r0") for i in range(50)]
    batch = select_stratified_batch("commits_judge", items, frozenset(), negative_cases, seed=1)
    batch_ids = {item.record_id for item in batch}
    assert "case_neg_a:commits_judge:0#r0" in batch_ids
    assert "case_neg_b:commits_judge:0#r0" in batch_ids


def test_positive_candidates_are_capped_at_the_negative_count() -> None:
    """50 available positive candidates against 2 negative ones yields a batch
    of 4 (2 negative + 2 sampled positive), not all 52 — the oversample, not a
    dump of everything unlabelled."""
    negative_cases = frozenset({"case_neg_a", "case_neg_b"})
    items = [
        _item("case_neg_a:commits_judge:0#r0"),
        _item("case_neg_b:commits_judge:0#r0"),
    ] + [_item(f"case_pos_{i:03d}:commits_judge:0#r0") for i in range(50)]
    batch = select_stratified_batch("commits_judge", items, frozenset(), negative_cases, seed=1)
    assert len(batch) == 4


def test_no_negative_candidates_keeps_every_positive_one() -> None:
    """When nothing is expected_negative, the batch is simply every unlabelled
    candidate — there is no minority stratum to cap against."""
    items = [_item(f"case_pos_{i:03d}:commits_judge:0#r0") for i in range(5)]
    batch = select_stratified_batch("commits_judge", items, frozenset(), frozenset(), seed=1)
    assert len(batch) == 5


def test_already_labelled_items_are_excluded() -> None:
    negative_cases = frozenset({"case_neg_a"})
    items = [_item("case_neg_a:commits_judge:0#r0"), _item("case_pos_a:commits_judge:0#r0")]
    already_labelled = frozenset({("case_neg_a:commits_judge:0#r0", "commits_judge")})
    batch = select_stratified_batch("commits_judge", items, already_labelled, negative_cases, seed=1)
    assert [item.record_id for item in batch] == ["case_pos_a:commits_judge:0#r0"]


def test_other_scorers_items_are_excluded() -> None:
    items = [_item("case_neg_a:tone_judge:0#r0", scorer="tone_judge"), _item("case_neg_a:commits_judge:0#r0")]
    negative_cases = frozenset({"case_neg_a"})
    batch = select_stratified_batch("commits_judge", items, frozenset(), negative_cases, seed=1)
    assert [item.record_id for item in batch] == ["case_neg_a:commits_judge:0#r0"]


def test_same_seed_is_reproducible() -> None:
    negative_cases = frozenset({"case_neg_a", "case_neg_b"})
    items = [
        _item("case_neg_a:commits_judge:0#r0"),
        _item("case_neg_b:commits_judge:0#r0"),
    ] + [_item(f"case_pos_{i:03d}:commits_judge:0#r0") for i in range(20)]
    first = select_stratified_batch("commits_judge", items, frozenset(), negative_cases, seed=42)
    second = select_stratified_batch("commits_judge", items, frozenset(), negative_cases, seed=42)
    assert [i.record_id for i in first] == [i.record_id for i in second]


def test_different_seeds_can_differ() -> None:
    negative_cases = frozenset({"case_neg_a", "case_neg_b"})
    items = [
        _item("case_neg_a:commits_judge:0#r0"),
        _item("case_neg_b:commits_judge:0#r0"),
    ] + [_item(f"case_pos_{i:03d}:commits_judge:0#r0") for i in range(20)]
    a = select_stratified_batch("commits_judge", items, frozenset(), negative_cases, seed=1)
    b = select_stratified_batch("commits_judge", items, frozenset(), negative_cases, seed=2)
    assert [i.record_id for i in a] != [i.record_id for i in b]
