"""
test_context_scoring_array_payloads.py - The scorer must read list-shaped context payloads.

Every item carrying an NPC's inner life is serialized as a JSON ARRAY of records:
`beliefs`, `goals`, `memories`, `secrets`, `obligations`, `owned_items`, `reputation`
(context_builder._build_tier_a_extended) and `nearby_npcs`, `traits`, `believed_rumors`
and the session turns elsewhere. `parse_json_object` returns `{}` for an array, so every
one of them scored recency 0.0 and severity 0.0 and was ranked on proximity and priority
alone -- while the four severity fallbacks written specifically FOR them
(severity/urgency/confidence/emotional_charge) could never be reached by any input.

Does NOT: execute I/O, touch the graph, or call LLM services.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from npc_engine.retrieval.context.context_score_extractors import (
    extract_recency_score as _extract_recency_score,
    extract_severity_score as _extract_severity_score,
    payload_for_scoring as _payload_for_scoring,
    quest_score as _quest_score,
)
from npc_engine.retrieval.context.context_merger import ContextItem


def _array_item(key: str, *records: dict[str, Any]) -> ContextItem:
    """A tier-A item shaped exactly as _build_tier_a_extended emits it."""
    return ContextItem(key=key, text=json.dumps(list(records)), tier="tierA", priority=88)


# ── _payload_for_scoring ─────────────────────────────────────────────────────


def test_an_object_payload_passes_through_unchanged() -> None:
    payload = {"severity": 40, "summary": "a fire in the market"}
    assert _payload_for_scoring(json.dumps(payload)) == payload


def test_an_array_payload_yields_its_first_record() -> None:
    """First, not merged: the producers ORDER BY the very field the scorer reads."""
    text = json.dumps([{"confidence": 92}, {"confidence": 10}])
    assert _payload_for_scoring(text) == {"confidence": 92}


def test_an_array_of_scalars_yields_no_payload() -> None:
    """Session turns are a list of strings -- there is nothing to score, and that is fine."""
    assert _payload_for_scoring(json.dumps(["hello there", "well met"])) == {}


def test_an_empty_array_yields_no_payload() -> None:
    assert _payload_for_scoring(json.dumps([])) == {}


def test_unparseable_text_yields_no_payload() -> None:
    assert _payload_for_scoring("not json at all") == {}


# ── the four severity fallbacks, each revived ────────────────────────────────


@pytest.mark.parametrize(
    ("key", "field", "raw", "expected"),
    [
        ("secrets", "severity", 80, 0.80),
        ("goals", "urgency", 75, 0.75),
        ("beliefs", "confidence", 92, 0.92),
        ("memories", "emotional_charge", -60, 0.60),
    ],
)
def test_each_severity_fallback_is_reachable_from_an_array_payload(
    key: str, field: str, raw: int, expected: float
) -> None:
    """Red before the fix: every one of these scored 0.0, for every NPC, on every turn."""
    item = _array_item(key, {field: raw, "content": "something the NPC holds"})
    assert _extract_severity_score(_payload_for_scoring(item.text)) == pytest.approx(expected)


def test_memory_emotional_charge_is_read_as_a_magnitude() -> None:
    """A bitter memory is as relevant as a fond one -- the sign must not cancel the score."""
    bitter = _array_item("memories", {"emotional_charge": -90})
    fond = _array_item("memories", {"emotional_charge": 90})
    bitter_score = _extract_severity_score(_payload_for_scoring(bitter.text))
    assert bitter_score == pytest.approx(0.90)
    assert bitter_score == pytest.approx(_extract_severity_score(_payload_for_scoring(fond.text)))


# ── recency ──────────────────────────────────────────────────────────────────


def test_an_array_payload_still_yields_a_recency_score() -> None:
    """Game-time recency is the highest-weighted term in every shipped profile."""
    item = _array_item(
        "beliefs",
        {"content": "the war is coming", "created_at_game_time": json.dumps(
            {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
        )},
    )
    from npc_engine.world.time_utils import TimePoint

    score = _extract_recency_score(
        _payload_for_scoring(item.text),
        game_time=TimePoint(year=1, season="spring", day=1, time_of_day="morning"),
        game_day_horizon=365,
    )
    assert score == pytest.approx(1.0)


# ── quest matching ───────────────────────────────────────────────────────────


def test_a_belief_about_the_quest_giver_can_match_the_active_quest() -> None:
    """_quest_score reads the same payload; an array had no values to match against."""
    item = _array_item("beliefs", {"content": "he lied to me", "subject_id": "innkeeper1"})
    assert _quest_score(item=item, active_quest={"giver_id": "innkeeper1"}) == 1.0
