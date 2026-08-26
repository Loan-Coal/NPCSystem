"""
test_context_scoring_declared_severity.py - ISSUE-206: score the field the table names.

An array payload is scored on ONE representative record, and until now that record was
always the first one and the field was whatever the generic fallback chain happened to hit
first. That is right where the producer's ORDER BY and the scorer's read agree:

    beliefs          ORDER BY confidence DESC   -> read confidence         aligned
    goals            ORDER BY urgency DESC      -> read urgency            aligned
    secrets          ORDER BY severity DESC     -> read severity           aligned
    believed_rumors  sorted by confidence DESC  -> read confidence         aligned

and wrong for the two where they do not:

    memories         ORDER BY vividness DESC    -> read emotional_charge   NOT aligned
    active_pledges   ORDER BY sworn_at_tick     -> read severity           NOT aligned

For those two the first record is the most VIVID memory and the most RECENTLY SWORN pledge,
whose severity-family value is whatever it happens to be -- so an NPC's most consequential
memory could rank below a vivid but trivial one. The declaration table now names the field
per slot and the scorer takes the maximum of it across records, which removes the
dependency on producer ordering entirely rather than papering over it.

Does NOT: execute I/O, touch the graph, or call LLM services.
"""

from __future__ import annotations

import json

import pytest

from npc_engine.retrieval.context.context_score_extractors import (
    extract_severity_score_for_item as _extract_severity_score_for_item,
)
from npc_engine.retrieval.context.context_slots import severity_field_for_key


def _text(payload: object) -> str:
    return json.dumps(payload)


def test_the_declared_field_beats_the_generic_fallback_chain() -> None:
    """`severity` sits first in the fallback chain and is not what memories are scored on."""
    payload = [{"severity": 10, "emotional_charge": 90, "vividness": 95}]
    assert _extract_severity_score_for_item("memories", _text(payload)) == pytest.approx(0.9)


def test_the_maximum_across_records_wins_not_the_first_one() -> None:
    """ISSUE-206's actual fix: ordering by vividness must not decide the severity score."""
    payload = [
        {"vividness": 95, "emotional_charge": 10},   # ordered first, barely charged
        {"vividness": 20, "emotional_charge": -95},  # the memory that actually matters
    ]
    assert _extract_severity_score_for_item("memories", _text(payload)) == pytest.approx(0.95)


def test_a_pledge_is_scored_on_severity_not_on_when_it_was_sworn() -> None:
    """active_pledges ORDER BY sworn_at_tick, so the first record is merely the newest."""
    payload = [
        {"sworn_at_tick": 900, "severity": 5},
        {"sworn_at_tick": 100, "severity": 95},
    ]
    assert _extract_severity_score_for_item("active_pledges", _text(payload)) == pytest.approx(0.95)


@pytest.mark.parametrize(
    ("key", "field", "value", "expected"),
    [
        ("beliefs", "confidence", 70, 0.70),
        ("goals", "urgency", 60, 0.60),
        ("secrets", "severity", 85, 0.85),
        ("believed_rumors", "confidence", 40, 0.40),
        ("traits", "intensity", 55, 0.55),
    ],
)
def test_the_aligned_slots_score_exactly_as_they_did(key, field, value, expected) -> None:
    """The four already-aligned producers must not move: this is a fix, not a re-weighting."""
    assert severity_field_for_key(key) == field
    assert _extract_severity_score_for_item(key, _text([{field: value}])) == pytest.approx(expected)


def test_a_negative_delta_is_scored_on_its_magnitude() -> None:
    """A reputation loss is as relevant as a gain of the same size."""
    payload = [{"reputation_delta": -30}]
    assert _extract_severity_score_for_item(
        "propagated_reputation", _text(payload)
    ) == pytest.approx(0.30)


def test_a_value_beyond_the_declared_range_clamps_rather_than_exceeding_one() -> None:
    """Graph data is external input; a mis-scaled field must not outrank everything."""
    assert _extract_severity_score_for_item("beliefs", _text([{"confidence": 5000}])) == 1.0


def test_a_key_with_no_declared_field_falls_back_to_the_generic_chain() -> None:
    """Events and undeclared keys keep the behaviour they have always had."""
    assert severity_field_for_key("nearby_npcs") is None
    assert _extract_severity_score_for_item(
        "nearby_npcs", _text([{"severity": 40}])
    ) == pytest.approx(0.40)


def test_a_missing_declared_field_falls_back_rather_than_scoring_zero() -> None:
    """A producer that stops emitting the field must degrade, not silently zero the slot."""
    payload = [{"severity": 60}]
    assert _extract_severity_score_for_item("memories", _text(payload)) == pytest.approx(0.60)


def test_an_object_payload_is_scored_on_the_declared_field_too() -> None:
    """`top_need` is a single object, not an array, and still declares its field."""
    assert severity_field_for_key("top_need") == "urgency"
    assert _extract_severity_score_for_item(
        "top_need", _text({"urgency": 80, "severity": 1})
    ) == pytest.approx(0.80)


def test_unparseable_text_scores_zero_without_raising() -> None:
    """Compression can truncate a payload mid-string; the scorer must survive it."""
    assert _extract_severity_score_for_item("memories", '{"summary":"...[compressed') == 0.0


def test_a_list_of_strings_scores_zero_without_raising() -> None:
    """`session` is an array of plain strings and must not be probed for fields."""
    assert _extract_severity_score_for_item("session", _text(["turn one", "turn two"])) == 0.0
