"""
test_json_fields.py - Unit tests for serialize_provenance_field.

Does NOT: connect to Neo4j or any external service.
"""

from __future__ import annotations

import json

import pytest

from npc_engine.graph.infra.json_fields import serialize_provenance_field


# ---------------------------------------------------------------------------
# serialize_provenance_field
# ---------------------------------------------------------------------------


def test_provenance_dict_is_serialized_to_json_string():
    payload = {"id": "npc_1", "provenance": {"source": "quest_engine", "version": 2}}
    result = serialize_provenance_field(payload)
    assert isinstance(result["provenance"], str)
    assert json.loads(result["provenance"]) == {"source": "quest_engine", "version": 2}


def test_other_fields_are_preserved_unchanged():
    payload = {"id": "npc_1", "name": "Aria", "provenance": {"source": "system"}}
    result = serialize_provenance_field(payload)
    assert result["id"] == "npc_1"
    assert result["name"] == "Aria"


def test_provenance_keys_are_sorted():
    payload = {"provenance": {"z_key": 1, "a_key": 2}}
    result = serialize_provenance_field(payload)
    serialized = result["provenance"]
    assert serialized.index("a_key") < serialized.index("z_key")


def test_no_provenance_field_returns_payload_unchanged():
    payload = {"id": "npc_1", "name": "Bob"}
    result = serialize_provenance_field(payload)
    assert result is payload


def test_provenance_not_a_dict_returns_payload_unchanged():
    payload = {"id": "npc_1", "provenance": "already-a-string"}
    result = serialize_provenance_field(payload)
    assert result is payload


def test_provenance_none_returns_payload_unchanged():
    payload = {"id": "npc_1", "provenance": None}
    result = serialize_provenance_field(payload)
    assert result is payload


def test_empty_provenance_dict_serializes_to_empty_json_object():
    payload = {"provenance": {}}
    result = serialize_provenance_field(payload)
    assert result["provenance"] == "{}"


def test_nested_provenance_dict_round_trips():
    nested = {"outer": {"inner": [1, 2, 3]}}
    payload = {"provenance": nested}
    result = serialize_provenance_field(payload)
    assert json.loads(result["provenance"]) == nested


def test_returns_new_dict_does_not_mutate_original():
    payload = {"id": "npc_1", "provenance": {"source": "test"}}
    result = serialize_provenance_field(payload)
    assert result is not payload
    assert isinstance(payload["provenance"], dict), "original should stay as dict"
