"""
test_context_pipeline.py - Unit tests for context merge, budget, and serialization pipeline.

Does NOT: execute graph queries.

Dependencies injected: None.
"""

import pytest
import json

from npc_engine.retrieval.context_merger import ContextItem, merge_context
from npc_engine.retrieval.context_serializer import serialize_context
from npc_engine.retrieval.token_budget_enforcer import TokenBudgetExceededError, enforce_budget


def test_merge_context_deduplicates_by_key_highest_priority() -> None:
    tier0 = [ContextItem(key="world", text="w", tier="tier0", priority=100)]
    tier_a = [ContextItem(key="event", text="older", tier="tierA", priority=10)]
    tier_b = [ContextItem(key="event", text="newer", tier="tierB", priority=20)]
    merged = merge_context(tier0=tier0, tier_a=tier_a, tier_b=tier_b)
    event_items = [item for item in merged.items if item.key == "event"]
    assert len(event_items) == 1
    assert event_items[0].text == "newer"


def test_serializer_is_deterministic() -> None:
    context = merge_context(
        tier0=[ContextItem(key="world", text="a", tier="tier0", priority=100)],
        tier_a=[ContextItem(key="bio", text="b", tier="tierA", priority=90)],
        tier_b=[],
    )
    first = serialize_context(context=context)
    second = serialize_context(context=context)
    assert first == second


def test_serializer_outputs_fixed_skeleton_keys() -> None:
    context = merge_context(
        tier0=[
            ContextItem(key="world", text='{"epoch":"age_of_peace"}', tier="tier0", priority=100),
            ContextItem(key="emotion", text='{"current_mood":"neutral"}', tier="tier0", priority=95),
            ContextItem(key="session", text='["hello"]', tier="tier0", priority=90),
        ],
        tier_a=[ContextItem(key="character:npc_1", text='{"name":"Aldric"}', tier="tierA", priority=80)],
        tier_b=[ContextItem(key="rag:npc_1", text='{"summary":"event"}', tier="tierB", priority=70)],
    )
    parsed = json.loads(serialize_context(context=context))
    expected_keys = {
        "world",
        "npc",
        "player_relation",
        "npc_known_events",
        "nearby_npcs",
        "recent_session_turns",
    }
    assert set(parsed.keys()) == expected_keys


def test_serializer_populates_player_relation_and_nearby_npcs() -> None:
    context = merge_context(
        tier0=[ContextItem(key="world", text='{"epoch":"age_of_peace"}', tier="tier0", priority=100)],
        tier_a=[
            ContextItem(key="character:npc_1", text='{"name":"Aldric"}', tier="tierA", priority=90),
            ContextItem(key="relation:player", text='{"trust":62,"fear":20}', tier="tierA", priority=85),
            ContextItem(key="nearby_npcs", text='[{"name":"Sera"}]', tier="tierA", priority=84),
            ContextItem(key="location:loc_market", text='{"name":"Grand Market"}', tier="tierA", priority=83),
        ],
        tier_b=[],
    )
    payload = json.loads(serialize_context(context=context))
    assert payload["player_relation"]["trust"] == 62
    assert payload["nearby_npcs"][0]["name"] == "Sera"
    assert payload["npc"]["profile"]["current_location"] == "Grand Market"


def test_budget_enforcer_rejects_tier0_overflow() -> None:
    merged = merge_context(
        tier0=[ContextItem(key="world", text="x" * 5000, tier="tier0", priority=100)],
        tier_a=[],
        tier_b=[],
    )
    with pytest.raises(TokenBudgetExceededError):
        enforce_budget(context=merged, budget=100)


def test_budget_enforcer_rejects_tier0_fixed_cap_overflow() -> None:
    merged = merge_context(
        tier0=[ContextItem(key="world", text="x" * 2000, tier="tier0", priority=100)],
        tier_a=[],
        tier_b=[],
    )
    with pytest.raises(TokenBudgetExceededError):
        enforce_budget(context=merged, budget=1000)


def test_budget_enforcer_trims_tier_b_first() -> None:
    merged = merge_context(
        tier0=[ContextItem(key="world", text="w" * 40, tier="tier0", priority=100)],
        tier_a=[ContextItem(key="a1", text="a" * 40, tier="tierA", priority=80)],
        tier_b=[ContextItem(key="b1", text="b" * 40, tier="tierB", priority=80)],
    )
    trimmed = enforce_budget(context=merged, budget=20)
    retained_keys = [item.key for item in trimmed.items]
    assert "a1" in retained_keys
    assert "b1" not in retained_keys


def test_budget_enforcer_rounding_prevents_budget_overshoot() -> None:
    merged = merge_context(
        tier0=[ContextItem(key="world", text="w" * 4, tier="tier0", priority=100)],
        tier_a=[ContextItem(key="a1", text="a" * 5, tier="tierA", priority=80)],
        tier_b=[],
    )
    trimmed = enforce_budget(context=merged, budget=2)
    retained_keys = [item.key for item in trimmed.items]
    assert retained_keys == ["world"]
