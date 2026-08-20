"""
Module: test_snapshot
Layer: demo_game (tests)
Purpose: Unit tests for snapshot export/restore logic (no Neo4j required).
Dependencies: demo_game.snapshot, unittest.mock, json, pathlib, pytest,
    demo_game.tests.conftest fakes
Used by: make test-demo
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from demo_game.tests.conftest import FakeDriver, FakeSession, world_clock_row
from demo_game.snapshot import (
    CYPHER_REMOVE_SNAP_PROP,
    CYPHER_WIPE,
    EXIT_LIVE_WRITER,
    EXIT_SNAPSHOT_MISSING,
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
    tx = MagicMock()
    nodes = [
        {"eid": "4:abc:0", "labels": ["NPC"], "props": {"id": "mira", "name": "Mira"}},
        {"eid": "4:abc:1", "labels": ["Location"], "props": {"id": "tavern"}},
    ]

    _restore_nodes(tx, nodes)

    assert tx.run.call_count == 2
    # First call: NPC node
    first_call_args = tx.run.call_args_list[0]
    cypher: str = first_call_args[0][0]
    props: dict = first_call_args[1]["props"]
    assert "`NPC`" in cypher
    assert props[_SNAP_EID_PROP] == "4:abc:0"
    assert props["id"] == "mira"


def test_restore_nodes_multiple_labels() -> None:
    tx = MagicMock()
    nodes = [{"eid": "4:abc:2", "labels": ["Person", "NPC"], "props": {}}]

    _restore_nodes(tx, nodes)

    cypher: str = tx.run.call_args[0][0]
    assert "`Person`" in cypher
    assert "`NPC`" in cypher


def test_restore_nodes_empty_labels_uses_fallback() -> None:
    tx = MagicMock()
    nodes = [{"eid": "4:abc:3", "labels": [], "props": {"id": "x"}}]

    _restore_nodes(tx, nodes)

    cypher: str = tx.run.call_args[0][0]
    assert "Node" in cypher


# ---------------------------------------------------------------------------
# _restore_rels
# ---------------------------------------------------------------------------


def test_restore_rels_creates_each_relationship() -> None:
    tx = MagicMock()
    rels = [
        {
            "src_eid": "4:abc:0",
            "dst_eid": "4:abc:1",
            "rel_type": "LOCATED_AT",
            "props": {"since": 1},
        }
    ]

    _restore_rels(tx, rels)

    assert tx.run.call_count == 1
    cypher: str = tx.run.call_args[0][0]
    assert "`LOCATED_AT`" in cypher
    assert "$src" in cypher
    assert "$dst" in cypher
    kwargs = tx.run.call_args[1]
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
#
# ISSUE-188: the restore must run as ONE transaction, and must refuse to start at
# all while another process is writing to the graph. The previous contract - a
# separate auto-commit transaction per node - is what turned a mid-restore
# constraint violation into a permanently half-restored world.
# ---------------------------------------------------------------------------


def _write_snapshot(tmp_path: Path) -> Path:
    """Write a two-node, one-relationship snapshot file and return its path."""
    payload = {
        "nodes": [
            {"eid": "4:x:0", "labels": ["WorldState"], "props": {"id": "world"}},
            {"eid": "4:x:1", "labels": ["NPC"], "props": {"id": "mira"}},
        ],
        "rels": [
            {"src_eid": "4:x:1", "dst_eid": "4:x:0", "rel_type": "KNOWS", "props": {}}
        ],
    }
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def restore_session(stable_graph, monkeypatch: pytest.MonkeyPatch) -> FakeSession:
    """A fake session over an idle graph, wired into do_restore's driver."""
    session = FakeSession(stable_graph)
    monkeypatch.setattr("demo_game.snapshot._open_driver", lambda: FakeDriver(session))
    return session


def test_do_restore_runs_everything_in_one_transaction(
    tmp_path: Path, restore_session: FakeSession, no_probe_sleep: None
) -> None:
    do_restore(_write_snapshot(tmp_path))

    assert restore_session.execute_write_count == 1
    # Nothing destructive may go through an auto-commit session.run.
    assert CYPHER_WIPE not in restore_session.session_calls
    assert not any("CREATE" in cypher for cypher in restore_session.session_calls)


def test_do_restore_order_is_wipe_nodes_rels_then_sentinel_strip(
    tmp_path: Path, restore_session: FakeSession, no_probe_sleep: None
) -> None:
    do_restore(_write_snapshot(tmp_path))

    assert restore_session.tx is not None
    cyphers = restore_session.tx.cyphers
    assert cyphers[0] == CYPHER_WIPE
    assert cyphers[-1] == CYPHER_REMOVE_SNAP_PROP
    node_creates = [i for i, c in enumerate(cyphers) if c.startswith("CREATE (n:")]
    rel_creates = [i for i, c in enumerate(cyphers) if c.startswith("MATCH (a)")]
    assert len(node_creates) == 2
    assert len(rel_creates) == 1
    assert max(node_creates) < min(rel_creates)


def test_do_restore_reports_the_restored_counts(
    tmp_path: Path, restore_session: FakeSession, no_probe_sleep: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    do_restore(_write_snapshot(tmp_path))

    assert "restored 2 nodes, 1 relationships" in capsys.readouterr().err


def test_do_restore_lets_a_constraint_error_out_so_the_write_rolls_back(
    tmp_path: Path, stable_graph, monkeypatch: pytest.MonkeyPatch, no_probe_sleep: None
) -> None:
    """Regression for the 2026-08-19 22:19 half-restore (139 of 248 nodes).

    The driver owns retries and the rollback; do_restore must not swallow the
    failure or drive the work function itself.
    """
    from neo4j.exceptions import ConstraintError

    session = FakeSession(stable_graph, fail_on="CREATE (n:")
    driver = FakeDriver(session)
    monkeypatch.setattr("demo_game.snapshot._open_driver", lambda: driver)

    with pytest.raises(ConstraintError):
        do_restore(_write_snapshot(tmp_path))

    assert session.execute_write_count == 1
    assert driver.closed is True


def test_do_restore_aborts_before_the_wipe_when_a_writer_is_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_probe_sleep: None
) -> None:
    session = FakeSession(
        [
            {"node_count": 248, "rel_count": 233, "clocks": [world_clock_row("world", 41)]},
            {"node_count": 248, "rel_count": 233, "clocks": [world_clock_row("world", 42)]},
        ]
    )
    monkeypatch.setattr("demo_game.snapshot._open_driver", lambda: FakeDriver(session))

    with pytest.raises(SystemExit) as excinfo:
        do_restore(_write_snapshot(tmp_path))

    assert excinfo.value.code == EXIT_LIVE_WRITER
    assert session.execute_write_count == 0
    assert session.tx is None
    assert CYPHER_WIPE not in session.session_calls


def test_live_writer_abort_names_the_change_and_the_remedy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_probe_sleep: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeSession(
        [
            {"node_count": 248, "rel_count": 233, "clocks": [world_clock_row("world", 41)]},
            {"node_count": 250, "rel_count": 233, "clocks": [world_clock_row("world", 41)]},
        ]
    )
    monkeypatch.setattr("demo_game.snapshot._open_driver", lambda: FakeDriver(session))

    with pytest.raises(SystemExit):
        do_restore(_write_snapshot(tmp_path))

    err = capsys.readouterr().err
    assert "node_count: 248 -> 250" in err
    assert "docker compose stop app" in err
    assert "Nothing was modified" in err


def test_do_restore_exits_if_snapshot_missing(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        do_restore(tmp_path / "nonexistent.json")

    assert excinfo.value.code == EXIT_SNAPSHOT_MISSING
