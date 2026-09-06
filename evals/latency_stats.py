"""
Module: latency_stats
Layer: evals (eval harness — not part of src/)
Purpose: Aggregate per-turn duration_ms into p50/p95 latency. duration_ms is
         captured per turn today (generation_collection.stamp_records) and was
         present in every row of the previous generation, but nothing aggregates
         it — every trend row's latency is unmeasured. A single engine call
         produces several GenerationRecords (one per expectation), all stamped
         with the same duration_ms, so this module dedupes to one duration per
         (case_id, repetition) turn before computing percentiles — counting each
         record would over-weight cases with more expectations.
Dependencies: math (stdlib), typing; transcript_models (GenerationRecord, for typing)
Used by: evals/trend_row_builder.py (TrendRow.latency_p50_ms / latency_p95_ms)
"""

from __future__ import annotations

import math
from typing import Sequence

from transcript_models import GenerationRecord


def unique_turn_durations(records: Sequence[GenerationRecord]) -> list[int]:
    """Dedupe GenerationRecords sharing one engine call to one duration per turn.

    A turn is identified by (case_id, repetition), where case_id is record_id's
    first ':'-delimited segment (mirrors label_adequacy._cluster_count). All
    records from one turn carry the same duration_ms (generation_collection.
    stamp_records stamps every expectation's record identically), so the first
    one seen per turn is kept and the rest are dropped.

    Args:
        records: GenerationRecords from one transcript; may span many turns and
            several expectations per turn.
    Returns:
        One duration_ms per distinct (case_id, repetition), in first-seen order.
    """
    seen: dict[tuple[str, int], int] = {}
    for record in records:
        case_id = record.record_id.split(":")[0]
        seen.setdefault((case_id, record.repetition), record.duration_ms)
    return list(seen.values())


def percentile(values: Sequence[int], pct: float) -> float | None:
    """Nearest-rank percentile over integer millisecond values.

    Args:
        values: Sample of duration_ms values; order does not matter.
        pct: Percentile in [0, 100].
    Returns:
        The pct-th percentile via the nearest-rank method
        (index ceil(pct/100 * n), 1-based), or None when values is empty.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return float(ordered[rank - 1])


def latency_summary(records: Sequence[GenerationRecord]) -> tuple[float | None, float | None]:
    """Compute (p50, p95) turn latency in milliseconds from raw transcript records.

    Args:
        records: GenerationRecords from one transcript (see unique_turn_durations
            for how duplicate per-expectation records are collapsed).
    Returns:
        (p50_ms, p95_ms); both None when records is empty.
    """
    durations = unique_turn_durations(records)
    return percentile(durations, 50.0), percentile(durations, 95.0)
