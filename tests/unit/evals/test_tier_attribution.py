"""
Module: tests.unit.evals.test_tier_attribution
Layer: test (unit)
Purpose: An A/B verdict that says "aggressive beat default" must be able to say WHERE the
         extra context came from. tier_spend on the context receipt is the only honest
         source of that, and nothing read it.
Dependencies: pytest; evals.tier_attribution, evals.context_receipt_record,
         evals.transcript_models
Used by: make test (pytest discovery)

Why not retrieved_context. GenerationRecord.retrieved_context comes from a SECOND call to
GET /v1/admin/debug/retrieval made after the dialogue turn, so it describes what the
retriever RANKED, not what reached the model (retrieved_item.py:17, ISSUE-195). Its every
item is also tier='unknown', a documented sentinel: build_serialized_context flattens tier
metadata and the endpoint cannot recover it. Attribution built on it would be fiction.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from context_receipt_record import ContextReceiptRecord, TierSpendRecord  # noqa: E402
from tier_attribution import (  # noqa: E402
    NO_TIER_SPEND,
    aggregate_tier_spend,
    format_tier_spend,
    read_tier_spend,
)
from transcript_models import GenerationRecord  # noqa: E402


def _record(*tiers: tuple[str, int, int]) -> GenerationRecord:
    """A minimal record carrying one receipt with the given (tier, items, tokens) triples."""
    return _bare_record().model_copy(
        update={
            "context_receipt": ContextReceiptRecord(
                retrieval_profile="default",
                tier_spend=tuple(
                    TierSpendRecord(tier=tier, items=items, tokens=tokens)
                    for tier, items, tokens in tiers
                ),
            )
        }
    )


def _bare_record() -> GenerationRecord:
    """A record with no receipt at all — every arm generated before the field existed."""
    return GenerationRecord(
        record_id="case_x:tone_judge:0",
        source="runner",
        npc_id="mira_innkeeper",
        player_id="player_eval",
        player_message="hello",
        npc_response="hello yourself",
        criteria="is it warm",
        judge_kind="tone_judge",
        expected_polarity="pass_on_yes",
    )


def test_spend_is_summed_per_tier_across_every_turn() -> None:
    spend = aggregate_tier_spend([
        _record(("tier0", 2, 100), ("tierA", 1, 50)),
        _record(("tier0", 3, 200), ("tierA", 4, 25)),
    ])

    assert spend == (
        TierSpendRecord(tier="tier0", items=5, tokens=300),
        TierSpendRecord(tier="tierA", items=5, tokens=75),
    )


def test_turns_that_reported_no_receipt_are_skipped_not_counted_as_zero() -> None:
    """A cached-context turn performed no assembly, so it has no spend to contribute.
    Counting it as a zero row would drag a per-tier average toward a turn that never
    assembled anything."""
    spend = aggregate_tier_spend([_record(("tierB", 1, 10)), _bare_record()])

    assert spend == (TierSpendRecord(tier="tierB", items=1, tokens=10),)


def test_an_arm_with_no_receipts_at_all_yields_nothing() -> None:
    assert aggregate_tier_spend([_bare_record()]) == ()
    assert aggregate_tier_spend([]) == ()


def test_tiers_keep_the_order_the_engine_reported_them_in() -> None:
    """The receipt lists tiers in assembly order and includes empty tiers on purpose, so
    first-seen order is the engine's own. Re-sorting by name would only accidentally agree."""
    spend = aggregate_tier_spend([_record(("tierC", 1, 1), ("tier0", 1, 1), ("tierA", 1, 1))])

    assert tuple(s.tier for s in spend) == ("tierC", "tier0", "tierA")


def test_empty_tiers_the_engine_reported_are_preserved() -> None:
    """An empty tier is evidence: it says the tier was consulted and contributed nothing,
    which is exactly the difference an A/B between two retrieval profiles is measuring."""
    spend = aggregate_tier_spend([_record(("tier0", 2, 100), ("tierB", 0, 0))])

    assert spend == (
        TierSpendRecord(tier="tier0", items=2, tokens=100),
        TierSpendRecord(tier="tierB", items=0, tokens=0),
    )


def test_format_names_every_tier_with_its_items_and_tokens() -> None:
    line = format_tier_spend((
        TierSpendRecord(tier="tier0", items=5, tokens=300),
        TierSpendRecord(tier="tierB", items=0, tokens=0),
    ))

    assert "tier0" in line and "5 items" in line and "300 tok" in line
    assert "tierB" in line and "0 items" in line


def test_format_says_so_out_loud_when_there_is_nothing_to_attribute() -> None:
    """A blank reads as "not checked". An arm with no receipts must say it has none."""
    assert format_tier_spend(()) == NO_TIER_SPEND


def test_reading_a_directory_with_no_transcript_yields_nothing(tmp_path: Path) -> None:
    """compare is routinely pointed at directories holding only judged rows, and an older
    arm has no receipts anyway. A missing transcript is an absence of evidence, not an error."""
    assert read_tier_spend(tmp_path) == ()
