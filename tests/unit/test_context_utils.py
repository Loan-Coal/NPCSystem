"""
Module: test_context_utils
Layer: retrieval (test)
Purpose: Regression tests for serialize_json temporal/non-native value handling.
Dependencies: npc_engine.retrieval.context_utils, neo4j.time, datetime.
Used by: pytest.
"""

from __future__ import annotations

import json
from datetime import datetime

from neo4j.time import DateTime as Neo4jDateTime

from npc_engine.retrieval.context_utils import serialize_json


def test_serialize_json_handles_python_datetime() -> None:
    payload = {"created_at": datetime(2026, 6, 8, 12, 30, 0)}
    result = serialize_json(payload)
    assert "2026-06-08T12:30:00" in result
    assert json.loads(result)["created_at"].startswith("2026-06-08T12:30:00")


def test_serialize_json_handles_neo4j_datetime() -> None:
    # Regression for ISSUE-079: a raw Neo4j DateTime in a second-hop event row used to
    # raise "Object of type DateTime is not JSON serializable" and degrade dialogue to canned.
    payload = {"happened_at": Neo4jDateTime(2026, 6, 8, 12, 30, 0)}
    result = serialize_json(payload, strip_nulls=True)
    assert "2026-06-08T12:30:00" in result


def test_serialize_json_handles_nested_temporal_in_list() -> None:
    payload = {"events": [{"ts": Neo4jDateTime(2026, 1, 2, 3, 4, 5)}]}
    result = serialize_json(payload)
    assert "2026-01-02T03:04:05" in result


def test_serialize_json_non_native_object_degrades_to_str() -> None:
    class Opaque:
        def __str__(self) -> str:
            return "opaque-value"

    result = serialize_json({"x": Opaque()})
    assert "opaque-value" in result
