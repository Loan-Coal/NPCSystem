"""
Module: tier_attribution
Layer: evals (eval harness — not part of src/)
Purpose: Per-tier item and token attribution for one generation arm, summed from the context
         receipts the engine returned, so an A/B verdict can say WHERE the context that
         produced it came from.
Dependencies: pathlib, typing; context_receipt_record (TierSpendRecord), eval_records
         (read_transcript, GenerationRecord)
Used by: evals/compare.py (the report's per-arm "Tiers" lines)
Does NOT: decide comparability, compute rates, or call the engine.

WHY THE RECEIPT IS THE ONLY SOURCE
`GenerationRecord.retrieved_context` looks like it would serve and does not: it comes from a
SECOND call to GET /v1/admin/debug/retrieval made after the dialogue turn, so it describes
what the retriever RANKED rather than what reached the model (retrieved_item.py:17,
ISSUE-195). Every item it carries is `tier='unknown'` — a documented sentinel, because
build_serialized_context flattens tier metadata and the endpoint cannot recover it.
Attribution built on it would be fiction. `context_receipt.tier_spend` is the engine's own
report of the assembly that actually produced the response.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from context_receipt_record import TierSpendRecord
from eval_records import GenerationRecord, read_transcript

__all__ = ["NO_TIER_SPEND", "aggregate_tier_spend", "format_tier_spend", "read_tier_spend"]

NO_TIER_SPEND: str = "no context receipts — this arm reported none"
"""Rendered when an arm carries no receipts at all.

Said out loud rather than printed as a blank: an empty line reads as "not checked", and an
arm that predates the receipt is a real caveat on any attribution claim made about it.
"""

_TRANSCRIPT_FILENAME: str = "outputs.jsonl"


def aggregate_tier_spend(records: Sequence[GenerationRecord]) -> tuple[TierSpendRecord, ...]:
    """Sum per-tier item and token spend across every turn that reported a receipt.

    Tiers keep the order the engine first reported them in, which is assembly order; empty
    tiers are preserved because the receipt includes them on purpose — a tier that was
    consulted and contributed nothing is exactly the difference an A/B between two retrieval
    profiles is measuring.

    Args:
        records: The arm's generation records, in transcript order.
    Returns:
        One TierSpendRecord per tier seen. Empty when no record carried a receipt; turns
        without one are skipped rather than counted as zero, since a cached-context turn
        performed no assembly and has no spend to contribute.
    """
    totals: dict[str, tuple[int, int]] = {}
    for record in records:
        if record.context_receipt is None:
            continue
        for tier in record.context_receipt.tier_spend:
            items, tokens = totals.get(tier.tier, (0, 0))
            totals[tier.tier] = (items + tier.items, tokens + tier.tokens)
    return tuple(
        TierSpendRecord(tier=tier, items=items, tokens=tokens)
        for tier, (items, tokens) in totals.items()
    )


def format_tier_spend(spend: Sequence[TierSpendRecord]) -> str:
    """Render aggregated tier spend as one report line.

    Args:
        spend: Aggregated per-tier spend, in report order.
    Returns:
        e.g. 'tier0 5 items / 300 tok; tierA 2 items / 180 tok', or NO_TIER_SPEND when empty.
    """
    if not spend:
        return NO_TIER_SPEND
    return "; ".join(f"{s.tier} {s.items} items / {s.tokens} tok" for s in spend)


def read_tier_spend(gen_dir: Path) -> tuple[TierSpendRecord, ...]:
    """Aggregate one generation directory's tier spend from its transcript.

    Args:
        gen_dir: A generation directory, which may hold judged rows but no transcript.
    Returns:
        The aggregated spend, or an empty tuple when the directory has no transcript —
        a missing transcript is an absence of evidence, not an error to raise at a caller
        that is only trying to describe an arm.
    """
    transcript_path = gen_dir / _TRANSCRIPT_FILENAME
    if not transcript_path.exists():
        return ()
    return aggregate_tier_spend(read_transcript(transcript_path).records)
