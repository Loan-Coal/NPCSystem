"""
test_context_serializer_generated.py - the skeleton is generated from the table, exactly.

Two things are pinned here and they pull in opposite directions, which is the point.

**The shape must not vary between turns.** `player_memories` used to be added to the
skeleton only when the item existed, so two NPCs who differed only in whether they had met
the player produced prompts with different SCHEMAS. In an A/B run that is schema drift
wearing a treatment effect's clothes: the arms differ structurally before anyone has
measured anything. Every enabled slot is now emitted every turn, empty default or not.

**The content must still be what it was.** A generated walk that quietly changed a payload
would be indistinguishable, from the eval's side, from a retrieval change. So the golden
skeleton below is asserted byte-for-byte.

Does NOT: execute I/O, touch the graph, call LLM services, or read configuration.
"""

from __future__ import annotations

import json

import pytest

from npc_engine.retrieval.context.context_merger import ContextItem, MergedContext
from npc_engine.retrieval.context.context_serializer import serialize_context
from npc_engine.retrieval.context.context_slots import CONTEXT_SLOTS, serialized_slots


def _item(key: str, payload: object, tier: str = "tierA", priority: int = 50) -> ContextItem:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return ContextItem(key=key, text=text, tier=tier, priority=priority)  # type: ignore[arg-type]


def _full_context() -> MergedContext:
    """One item for every enabled slot, so the golden covers the whole table."""
    return MergedContext(items=[
        _item("world", {"epoch": "war", "year": 812}, tier="tier0", priority=100),
        _item("system_state", {"npc_can_trade": False}, tier="tier0", priority=97),
        _item("emotion", {"current_mood": "agitated"}, tier="tier0", priority=95),
        _item("character:mira_innkeeper", {"id": "mira_innkeeper", "name": "Mira"}),
        _item("session", ["player: hello", "npc: well met"]),
        _item("relation:player", {"trust": 40, "fear": 0}),
        _item("location:loc_tavern", {"id": "loc_tavern", "name": "The Broken Oar", "desc": "loud"}),
        _item("nearby_npcs", [{"id": "lira_fence"}]),
        _item("player_memories", [{"summary": "he paid his tab"}]),
        _item("memories", [{"summary": "the fire", "emotional_charge": 80}]),
        _item("event:0:mira_innkeeper", {"id": "e1", "summary": "war began", "severity": 90}),
        _item("event:1:mira_innkeeper", {"id": "e2", "summary": "a festival", "severity": 20}),
        _item("active_quest", {"quest_id": "q_find_the_ledger"}),
        _item("beliefs", [{"content": "the guard lies", "confidence": 70}]),
        _item("goals", [{"content": "keep the inn open", "urgency": 60}]),
        _item("reputation", [{"faction_id": "city_guard", "standing": -10}]),
        _item("propagated_reputation", [{"faction_id": "thieves_guild", "reputation_delta": -30,
                                         "account": "word is he knifed a guildsman",
                                         "knowledge_state": "rumor"}]),
        _item("top_need", {"need_type": "safety", "urgency": 80}, tier="tierB", priority=60),
        _item("rag:node_7", {"id": "node_7", "summary": "the northern road is closed"},
              tier="tierB", priority=60),
    ])


GOLDEN_FULL = (
    '{"active_quest":{"quest_id":"q_find_the_ledger"},'
    '"nearby_npcs":[{"id":"lira_fence"}],'
    '"npc":{"beliefs":[{"confidence":70,"content":"the guard lies"}],'
    '"emotion":{"current_mood":"agitated"},'
    '"goals":[{"content":"keep the inn open","urgency":60}],'
    '"memories":[{"emotional_charge":80,"summary":"the fire"}],'
    '"player_memories":[{"summary":"he paid his tab"}],'
    '"profile":{"current_location":"The Broken Oar","id":"mira_innkeeper","name":"Mira"},'
    '"top_need":{"need_type":"safety","urgency":80}},'
    '"npc_known_events":[{"id":"e1","severity":90,"summary":"war began"},'
    '{"id":"e2","severity":20,"summary":"a festival"}],'
    '"player_relation":{"fear":0,"trust":40},'
    '"player_reputation":[{"faction_id":"city_guard","standing":-10}],'
    '"propagated_reputation":[{"account":"word is he knifed a guildsman",'
    '"faction_id":"thieves_guild","knowledge_state":"rumor","reputation_delta":-30}],'
    '"recent_session_turns":["player: hello","npc: well met"],'
    '"retrieved_context":[{"id":"node_7","summary":"the northern road is closed"}],'
    '"system_state":{"npc_can_trade":false},'
    '"world":{"epoch":"war","year":812}}'
)


GOLDEN_EMPTY = (
    '{"active_quest":{},'
    '"nearby_npcs":[],'
    '"npc":{"beliefs":[],"emotion":{},"goals":[],"memories":[],"player_memories":[],'
    '"profile":{"current_location":null},"top_need":null},'
    '"npc_known_events":[],'
    '"player_relation":{},'
    '"player_reputation":[],'
    '"propagated_reputation":[],'
    '"recent_session_turns":[],'
    '"retrieved_context":[],'
    '"system_state":{},'
    '"world":{}}'
)


def test_a_full_context_serializes_to_the_golden_skeleton() -> None:
    """Byte-for-byte. A quiet payload change here is indistinguishable from a RAG change."""
    assert serialize_context(context=_full_context()) == GOLDEN_FULL


def test_an_empty_context_still_emits_every_enabled_slot() -> None:
    """Review point D: the prompt's SHAPE must not depend on what this NPC happens to have."""
    assert serialize_context(context=MergedContext(items=[])) == GOLDEN_EMPTY


def test_the_two_goldens_have_identical_slot_structure() -> None:
    """The previous test's claim as a property: same slots, whether or not they have data.

    Compares the SLOT paths the table declares, not every leaf inside a payload -- the
    payloads are graph content and are supposed to differ. Schema drift lives at the slot
    level, which is where the two arms of an A/B run would diverge structurally.
    """
    full = json.loads(GOLDEN_FULL)
    empty = json.loads(GOLDEN_EMPTY)
    assert set(full) == set(empty)
    assert set(full["npc"]) == set(empty["npc"])


def test_a_rag_hit_never_lands_in_the_authoritative_knowledge_list() -> None:
    """D10, half one, asserted on the output rather than on the table.

    system_v1.yaml calls npc_known_events authoritative -- "Do NOT reference any event,
    person, or fact not present in context.npc_known_events" -- and prompt_builder promotes
    anything in it carrying `distorted_summary` into a MY_ACCOUNT line, which the prompt
    calls "the exact words you would speak". A retrieved node is not an event this NPC
    witnessed. Concatenating them manufactures memory.
    """
    context = MergedContext(items=[
        _item("event:0:npc_a", {"id": "e1", "summary": "a real event"}),
        _item("rag:node_9", {"id": "node_9", "summary": "someone else's business",
                             "distorted_summary": "the words I would speak"},
              tier="tierB", priority=60),
    ])
    skeleton = json.loads(serialize_context(context=context))
    assert skeleton["npc_known_events"] == [{"id": "e1", "summary": "a real event"}]
    assert [row["id"] for row in skeleton["retrieved_context"]] == ["node_9"]


def test_a_withheld_slot_is_produced_but_not_serialized() -> None:
    """default_enabled=False must mean absent from the skeleton, not empty in it.

    An empty key would teach the model the NPC HAS no secrets, which is a different claim
    from the engine declining to tell it.
    """
    context = MergedContext(items=[_item("secrets", [{"content": "the ledger is forged"}])])
    skeleton = json.loads(serialize_context(context=context))
    assert "npc" in skeleton
    assert "secrets" not in skeleton["npc"]
    assert "the ledger is forged" not in json.dumps(skeleton)


def test_the_first_matching_item_wins_for_a_prefix_slot() -> None:
    """`character:` and `location:` are prefix_first; two matches must not merge."""
    context = MergedContext(items=[
        _item("character:a", {"name": "First"}),
        _item("character:b", {"name": "Second"}),
    ])
    skeleton = json.loads(serialize_context(context=context))
    assert skeleton["npc"]["profile"]["name"] == "First"


def test_a_payload_of_the_wrong_json_type_falls_back_to_the_slot_default() -> None:
    """Graph readers are external input; a list where an object belongs must not crash."""
    context = MergedContext(items=[
        _item("world", [1, 2, 3], tier="tier0", priority=100),
        _item("beliefs", {"not": "a list"}),
        _item("nearby_npcs", "unparseable text"),
    ])
    skeleton = json.loads(serialize_context(context=context))
    assert skeleton["world"] == {}
    assert skeleton["npc"]["beliefs"] == []
    assert skeleton["nearby_npcs"] == []


def test_location_contributes_only_its_name() -> None:
    """The location node is thousands of tokens and owes the prompt exactly one string."""
    context = MergedContext(items=[
        _item("character:x", {"id": "x"}),
        _item("location:loc_1", {"id": "loc_1", "name": "The Broken Oar",
                                 "description": "x" * 5000}),
    ])
    skeleton = json.loads(serialize_context(context=context))
    assert skeleton["npc"]["profile"]["current_location"] == "The Broken Oar"
    assert "x" * 100 not in json.dumps(skeleton)


@pytest.mark.parametrize("slot", [s for s in CONTEXT_SLOTS if s.default_enabled])
def test_every_enabled_slot_appears_in_the_empty_skeleton(slot) -> None:
    """The table IS the schema: adding a row must change the output with no other edit."""
    if slot.key == "system_state":
        pytest.skip("tier-0 producer omits the item entirely; covered by GOLDEN_EMPTY")
    skeleton = json.loads(serialize_context(context=MergedContext(items=[])))
    node: object = skeleton
    assert slot.path is not None
    for part in slot.path.split("."):
        assert isinstance(node, dict) and part in node, f"{slot.path} missing from skeleton"
        node = node[part]


def test_serialized_slots_is_a_strict_subset_of_the_table() -> None:
    """Guards the derivation itself, so a filter bug cannot silently enable everything."""
    assert set(serialized_slots()) <= set(CONTEXT_SLOTS)
    assert len(serialized_slots()) < len(CONTEXT_SLOTS)
