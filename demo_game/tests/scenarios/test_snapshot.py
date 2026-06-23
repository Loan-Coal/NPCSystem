"""
Module: test_snapshot
Layer: demo_game (tests)
Purpose: Unit tests for snapshot export/restore logic (no Neo4j required).
Dependencies: demo_game.snapshot, unittest.mock, json, pathlib, pytest
Used by: make test-demo
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from demo_game.snapshot import (
    DEFAULT_SNAPSHOT_PATH,
    _SNAP_EID_PROP,
    _deserialize_props,
    _deserialize_value,
    _restore_nodes,
    _restore_rels,
    _serialize_props,
    _serialize_value,
    do_restore,
    do_snapshot,
)


# ---------------------------------------------------------------------------
# _serialize_value
# ---------------------------------------------------------------------------


def test_serialize_value_primitives() -> None:
    assert _serialize_value("hello") == "hello"
    assert _serialize_value(42) == 42
    assert _serialize_value(3.14) == 3.14
    assert _serialize_value(True) is True
    assert _serialize_value(None) is None


def test_serialize_value_list() -> None:
    assert _serialize_value([1, "two", None]) == [1, "two", None]


def test_serialize_value_dict() -> None:
    assert _serialize_value({"a": 1, "b": "x"}) == {"a": 1, "b": "x"}


def test_serialize_value_neo4j_temporal() -> None:
    mock_dt = MagicMock()
    mock_dt.iso_format.return_value = "2026-06-02T12:00:00"
    type(mock_dt).__name__ = "DateTime"

    result = _serialize_value(mock_dt)

    assert result == {"__neo4j_type__": "DateTime", "value": "2026-06-02T12:00:00"}


def test_serialize_value_unknown_falls_back_to_str() -> None:
    class Weird:
        def __str__(self) -> str:
            return "weird"

    assert _serialize_value(Weird()) == "weird"


# ---------------------------------------------------------------------------
# _deserialize_value
# ---------------------------------------------------------------------------


def test_deserialize_value_plain_passthrough() -> None:
    assert _deserialize_value("hello") == "hello"
    assert _deserialize_value(99) == 99


def test_deserialize_value_type_tagged_returns_iso_string() -> None:
    tagged = {"__neo4j_type__": "DateTime", "value": "2026-06-02T12:00:00"}
    assert _deserialize_value(tagged) == "2026-06-02T12:00:00"


def test_deserialize_value_list() -> None:
    tagged = [{"__neo4j_type__": "Date", "value": "2026-06-02"}, "plain"]
    assert _deserialize_value(tagged) == ["2026-06-02", "plain"]


def test_deserialize_value_plain_dict_preserved() -> None:
    d = {"key": "value", "num": 7}
    assert _deserialize_value(d) == d


# ---------------------------------------------------------------------------
# Round-trip: serialize → deserialize
# ---------------------------------------------------------------------------


def test_roundtrip_plain_props() -> None:
    props = {"name": "Mira", "trust": 80, "active": True, "alias": None}
    assert _deserialize_props(_serialize_props(props)) == props


def test_roundtrip_temporal_prop_becomes_string() -> None:
    mock_dt = MagicMock()
    mock_dt.iso_format.return_value = "2026-06-02T12:00:00"
    type(mock_dt).__name__ = "DateTime"

    serialized = _serialize_props({"created_at": mock_dt})
    restored = _deserialize_props(serialized)
    # temporal value survives as its ISO string
    assert restored == {"created_at": "2026-06-02T12:00:00"}


# ---------------------------------------------------------------------------
# _restore_nodes
# ---------------------------------------------------------------------------


def test_restore_nodes_creates_each_node() -> None:
    session = MagicMock()
    nodes = [
        {"eid": "4:abc:0", "labels": ["NPC"], "props": {"id": "mira", "name": "Mira"}},
        {"eid": "4:abc:1", "labels": ["Location"], "props": {"id": "tavern"}},
    ]

    _restore_nodes(session, nodes)

    assert session.run.call_count == 2
    # First call: NPC node
    first_call_args = session.run.call_args_list[0]
    cypher: str = first_call_args[0][0]
    props: dict = first_call_args[1]["props"]
    assert "`NPC`" in cypher
    assert props[_SNAP_EID_PROP] == "4:abc:0"
    assert props["id"] == "mira"


def test_restore_nodes_multiple_labels() -> None:
    session = MagicMock()
    nodes = [{"eid": "4:abc:2", "labels": ["Person", "NPC"], "props": {}}]

    _restore_nodes(session, nodes)

    cypher: str = session.run.call_args[0][0]
    assert "`Person`" in cypher
    assert "`NPC`" in cypher


def test_restore_nodes_empty_labels_uses_fallback() -> None:
    session = MagicMock()
    nodes = [{"eid": "4:abc:3", "labels": [], "props": {"id": "x"}}]

    _restore_nodes(session, nodes)

    cypher: str = session.run.call_args[0][0]
    assert "Node" in cypher


# ---------------------------------------------------------------------------
# _restore_rels
# ---------------------------------------------------------------------------


def test_restore_rels_creates_each_relationship() -> None:
    session = MagicMock()
    rels = [
        {
            "src_eid": "4:abc:0",
            "dst_eid": "4:abc:1",
            "rel_type": "LOCATED_AT",
            "props": {"since": 1},
        }
    ]

    _restore_rels(session, rels)

    assert session.run.call_count == 1
    cypher: str = session.run.call_args[0][0]
    assert "`LOCATED_AT`" in cypher
    assert "$src" in cypher
    assert "$dst" in cypher
    kwargs = session.run.call_args[1]
    assert kwargs["src"] == "4:abc:0"
    assert kwargs["dst"] == "4:abc:1"
    assert kwargs["props"] == {"since": 1}


# ---------------------------------------------------------------------------
# do_snapshot (integration-style, mocked driver)
# ---------------------------------------------------------------------------


def _make_record(data: dict[str, Any]) -> MagicMock:
    rec = MagicMock()
    rec.__getitem__ = lambda self, key: data[key]
    return rec


def test_do_snapshot_writes_json(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "snap.json"

    node_rec = _make_record(
        {"eid": "4:x:0", "labels": ["NPC"], "props": {"id": "mira"}}
    )
    rel_rec = _make_record(
        {
            "src_eid": "4:x:0",
            "dst_eid": "4:x:1",
            "rel_type": "KNOWS",
            "props": {},
        }
    )

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.run.side_effect = [[node_rec], [rel_rec]]

    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session
    mock_driver.close = MagicMock()

    with patch("demo_game.snapshot._open_driver", return_value=mock_driver):
        do_snapshot(snapshot_path)

    assert snapshot_path.exists()
    payload = json.loads(snapshot_path.read_text())
    assert len(payload["nodes"]) == 1
    assert payload["nodes"][0]["eid"] == "4:x:0"
    assert len(payload["rels"]) == 1
    assert payload["rels"][0]["rel_type"] == "KNOWS"


# ---------------------------------------------------------------------------
# do_restore (integration-style, mocked driver + snapshot file)
# ---------------------------------------------------------------------------


def test_do_restore_reads_snapshot_and_recreates_graph(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "snap.json"
    payload = {
        "nodes": [{"eid": "4:x:0", "labels": ["NPC"], "props": {"id": "mira"}}],
        "rels": [
            {
                "src_eid": "4:x:0",
                "dst_eid": "4:x:1",
                "rel_type": "KNOWS",
                "props": {},
            }
        ],
    }
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session
    mock_driver.close = MagicMock()

    with patch("demo_game.snapshot._open_driver", return_value=mock_driver):
        do_restore(snapshot_path)

    # session.run calls: wipe, 1 node create, 1 rel create, remove snap prop
    assert mock_session.run.call_count == 4


def test_do_restore_exits_if_snapshot_missing(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        do_restore(tmp_path / "nonexistent.json")
