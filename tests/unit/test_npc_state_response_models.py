"""
test_npc_state_response_models.py - Unit tests for S20.2 typed NPCStateResponse.

Asserts that NPCStateResponse no longer carries raw `dict`/`list[dict]` fields:
its `character`, `relations`, and `events` fields are typed Pydantic sub-models
(CharacterNode, RelationEdge, EventNode). Also asserts the serialised wire shape
is unchanged (nested dicts), so the HTTP response body is byte-compatible.

Does NOT: touch Neo4j or the FastAPI app.
"""

from __future__ import annotations

from npc_engine.api.response_models.npc_state import CharacterNode, EventNode, RelationEdge
from npc_engine.api.schemas import NPCStateResponse


def test_character_node_allows_dynamic_registry_fields():
    """CharacterNode keeps the required id but allows registry-dynamic extra props."""
    node = CharacterNode(id="mira_innkeeper", name="Mira", archetype="merchant")
    dumped = node.model_dump()
    assert dumped["id"] == "mira_innkeeper"
    assert dumped["name"] == "Mira"
    assert dumped["archetype"] == "merchant"


def test_npc_state_response_coerces_dicts_into_typed_models():
    """Constructing from the graph-reader dict shape yields typed sub-models."""
    resp = NPCStateResponse(
        character={"id": "mira_innkeeper", "name": "Mira"},
        relations=[{"relation": {"trust": 50}, "character": {"id": "aldric_merchant"}}],
        events=[{"event": {"id": "ev1"}, "knowledge_state": "direct", "distorted_summary": None}],
    )
    assert isinstance(resp.character, CharacterNode)
    assert isinstance(resp.relations[0], RelationEdge)
    assert isinstance(resp.relations[0].character, CharacterNode)
    assert isinstance(resp.events[0], EventNode)
    assert resp.events[0].knowledge_state == "direct"


def test_npc_state_response_wire_shape_unchanged():
    """model_dump must reproduce the original nested-dict wire shape."""
    resp = NPCStateResponse(
        character={"id": "mira_innkeeper"},
        relations=[{"relation": {"trust": 50}, "character": {"id": "aldric_merchant"}}],
        events=[{"event": {"id": "ev1"}, "knowledge_state": "direct", "distorted_summary": "fuzzy"}],
    )
    dumped = resp.model_dump()
    assert dumped["character"] == {"id": "mira_innkeeper"}
    assert dumped["relations"][0]["relation"] == {"trust": 50}
    assert dumped["relations"][0]["character"] == {"id": "aldric_merchant"}
    assert dumped["events"][0]["event"] == {"id": "ev1"}
    assert dumped["events"][0]["knowledge_state"] == "direct"


def test_npc_state_response_character_optional():
    """character may be None (unknown NPC)."""
    resp = NPCStateResponse(character=None, relations=[], events=[])
    assert resp.character is None
