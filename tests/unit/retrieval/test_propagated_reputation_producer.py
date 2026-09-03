"""
test_propagated_reputation_producer.py - the slot the prompt teaches must have a producer.

`system_v1.yaml` Rule 13 is ~19 lines instructing the model how to read
`context.propagated_reputation` -- which faction, which delta, how to hedge a rumour versus
confirmed word, how to pitch the greeting. The serializer has always read the slot. Nothing
ever wrote it: `get_propagated_reputation_for_npc` is fully unit-tested in
`tests/unit/graph/test_reputation_queries_propagated.py` and had ZERO callers, so the list
was `[]` in 975 of 975 recorded rows and every one of those 19 lines was dead weight.

Does NOT: execute I/O, touch the graph, or call LLM services. The reader is stubbed.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.retrieval.context import context_graph_readers
from npc_engine.retrieval.context.context_builder import _build_tier_a_extended
from npc_engine.retrieval.context.context_graph_readers import _fetch_player_data
from npc_engine.config import Settings


def _rows() -> list[dict[str, Any]]:
    """Two rows shaped exactly as CYPHER_PROPAGATED_REPUTATION_FOR_NPC returns them."""
    return [
        {
            "faction_id": "thieves_guild",
            "reputation_delta": -30,
            "account": "word is the stranger knifed a guildsman in the market",
            "knowledge_state": "rumor",
        },
        {
            "faction_id": "city_guard",
            "reputation_delta": 15,
            "account": "the stranger turned in a cutpurse",
            "knowledge_state": "knows",
        },
    ]


def _extended(propagated: list[dict[str, Any]] | None) -> list[Any]:
    """Build the extended tier-A items with everything but propagated reputation empty."""
    return _build_tier_a_extended(
        "player_1", [], None, None, [], [], [], [], [], [], [],
        Settings(NEO4J_PASSWORD="not_the_default_pw"), "mira_innkeeper", None,
        propagated_reputation=propagated,
    )


def test_a_propagated_reputation_row_becomes_a_context_item() -> None:
    """Red before the producer existed: the key was never emitted by anything."""
    keys = [item.key for item in _extended(_rows())]
    assert "propagated_reputation" in keys


def test_the_item_carries_the_four_fields_rule_13_names() -> None:
    """Rule 13 reads faction_id, reputation_delta, account and knowledge_state by name."""
    item = next(i for i in _extended(_rows()) if i.key == "propagated_reputation")
    for field in ("faction_id", "reputation_delta", "account", "knowledge_state"):
        assert field in item.text, f"Rule 13 reads {field!r} and the payload does not carry it"


def test_no_propagated_reputation_means_no_item() -> None:
    """An empty read must not spend budget on an empty list."""
    assert [i for i in _extended([]) if i.key == "propagated_reputation"] == []
    assert [i for i in _extended(None) if i.key == "propagated_reputation"] == []


@pytest.mark.asyncio
async def test_the_reader_is_called_with_the_npc_and_the_player(monkeypatch) -> None:
    """The fetch stage must actually consult the reader, not just leave room for it."""
    seen: dict[str, Any] = {}

    async def fake_propagated(session: Any, **kwargs: Any) -> list[dict[str, Any]]:
        seen.update(kwargs)
        return _rows()

    async def empty(*args: Any, **kwargs: Any) -> Any:
        return []

    async def none_(*args: Any, **kwargs: Any) -> Any:
        return None

    monkeypatch.setattr(context_graph_readers, "get_propagated_reputation_for_npc", fake_propagated)
    monkeypatch.setattr(context_graph_readers, "get_trust_scores_for_events", empty)
    monkeypatch.setattr(context_graph_readers, "get_second_hop_events", empty)
    monkeypatch.setattr(context_graph_readers, "get_active_quest_for_player", none_)
    monkeypatch.setattr(context_graph_readers, "get_npc_player_edge", none_)

    result = await _fetch_player_data(object(), "mira_innkeeper", "player_1", [])

    assert seen == {"npc_id": "mira_innkeeper", "player_id": "player_1"}
    assert result[4] == _rows()


@pytest.mark.asyncio
async def test_an_anonymous_turn_does_not_read_propagated_reputation(monkeypatch) -> None:
    """No player means no player-scoped reputation, and no wasted round trip."""
    called = False

    async def fake_propagated(session: Any, **kwargs: Any) -> list[dict[str, Any]]:
        nonlocal called
        called = True
        return _rows()

    async def empty(*args: Any, **kwargs: Any) -> Any:
        return []

    monkeypatch.setattr(context_graph_readers, "get_propagated_reputation_for_npc", fake_propagated)
    monkeypatch.setattr(context_graph_readers, "get_trust_scores_for_events", empty)
    monkeypatch.setattr(context_graph_readers, "get_second_hop_events", empty)

    result = await _fetch_player_data(object(), "mira_innkeeper", None, [])

    assert called is False
    assert result[4] == []
