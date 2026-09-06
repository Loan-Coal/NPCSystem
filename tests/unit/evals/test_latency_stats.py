"""
Module: test_latency_stats
Layer: test (unit)
Purpose: Pin latency_stats's percentile math against hand-computed values, and pin
         the turn-dedup rule: one engine call produces several GenerationRecords
         (one per expectation) sharing one duration_ms, and counting each of them
         would over-weight cases with more expectations. duration_ms is captured
         per turn today (generation_collection.stamp_records) but was never
         aggregated — every trend row's latency is currently unmeasured.
Dependencies: pytest, latency_stats (evals/), transcript_models (GenerationRecord)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from latency_stats import latency_summary, percentile, unique_turn_durations
from transcript_models import GenerationRecord


def _record(case: str, kind: str, index: int, repetition: int, duration_ms: int) -> GenerationRecord:
    return GenerationRecord(
        record_id=f"{case}:{kind}:{index}",
        source="runner",
        npc_id="npc",
        player_id="player",
        player_message="hi",
        npc_response="hello",
        criteria="",
        judge_kind=None,
        expected_polarity="pass_on_yes",
        repetition=repetition,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# percentile — hand-computed, nearest-rank method
# ---------------------------------------------------------------------------


def test_percentile_p50_of_four_values() -> None:
    """[10, 20, 30, 40]: ceil(0.5*4)=2nd smallest -> 20."""
    assert percentile([40, 10, 30, 20], 50.0) == 20.0


def test_percentile_p95_of_twenty_values() -> None:
    """1..20 ms: ceil(0.95*20)=19th smallest -> 19."""
    assert percentile(list(range(1, 21)), 95.0) == 19.0


def test_percentile_of_a_single_value_is_that_value() -> None:
    assert percentile([500], 50.0) == 500.0
    assert percentile([500], 95.0) == 500.0


def test_percentile_of_empty_is_none() -> None:
    assert percentile([], 50.0) is None


# ---------------------------------------------------------------------------
# unique_turn_durations — dedup by (case_id, repetition), not by record
# ---------------------------------------------------------------------------


def test_records_from_one_turn_collapse_to_one_duration() -> None:
    """3 expectations on the same call all carry duration_ms=150 -> counted once."""
    records = [
        _record("case_001", "schema", 0, repetition=0, duration_ms=150),
        _record("case_001", "keyword_none", 1, repetition=0, duration_ms=150),
        _record("case_001", "tone_judge", 2, repetition=0, duration_ms=150),
    ]
    assert unique_turn_durations(records) == [150]


def test_different_repetitions_of_the_same_case_are_distinct_turns() -> None:
    records = [
        _record("case_001", "schema", 0, repetition=0, duration_ms=100),
        _record("case_001", "schema", 0, repetition=1, duration_ms=200),
    ]
    assert sorted(unique_turn_durations(records)) == [100, 200]


def test_different_cases_are_distinct_turns() -> None:
    records = [
        _record("case_001", "schema", 0, repetition=0, duration_ms=100),
        _record("case_002", "schema", 0, repetition=0, duration_ms=300),
    ]
    assert sorted(unique_turn_durations(records)) == [100, 300]


# ---------------------------------------------------------------------------
# latency_summary — the composed p50/p95, hand-computed end to end
# ---------------------------------------------------------------------------


def test_latency_summary_hand_computed() -> None:
    """3 turns at 100/200/300 ms (each with 2 duplicate expectation records):
    unique durations [100, 200, 300] -> p50=200 (2nd of 3), p95=300 (3rd of 3).
    """
    records = [
        _record("case_a", "schema", 0, repetition=0, duration_ms=100),
        _record("case_a", "keyword_none", 1, repetition=0, duration_ms=100),
        _record("case_b", "schema", 0, repetition=0, duration_ms=200),
        _record("case_b", "keyword_none", 1, repetition=0, duration_ms=200),
        _record("case_c", "schema", 0, repetition=0, duration_ms=300),
        _record("case_c", "keyword_none", 1, repetition=0, duration_ms=300),
    ]
    p50, p95 = latency_summary(records)
    assert p50 == 200.0
    assert p95 == 300.0


def test_latency_summary_of_no_records_is_none() -> None:
    assert latency_summary([]) == (None, None)
