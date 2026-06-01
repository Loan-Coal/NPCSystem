"""
test_engine_status_store.py - Unit tests for EngineStatusStore.

Does NOT: exercise real Neo4j or async I/O.
"""

from __future__ import annotations

import pytest

from npc_engine.scheduler.engine_status_store import EngineStatusRecord, EngineStatusStore


def test_initial_state_is_empty() -> None:
    store = EngineStatusStore()
    assert store.get_all() == {}


def test_record_success_sets_last_tick_id() -> None:
    store = EngineStatusStore()
    store.record_success("gossip", 5)
    record = store.get("gossip")
    assert record is not None
    assert record.last_tick_id == 5


def test_record_success_preserves_last_error() -> None:
    store = EngineStatusStore()
    store.record_error("gossip", 3, "initial error")
    store.record_success("gossip", 5)
    record = store.get("gossip")
    assert record is not None
    assert record.last_error == "initial error"
    assert record.last_error_tick == 3


def test_record_error_sets_last_error() -> None:
    store = EngineStatusStore()
    store.record_error("gossip", 5, "boom")
    record = store.get("gossip")
    assert record is not None
    assert record.last_error == "boom"
    assert record.last_error_tick == 5


def test_record_error_does_not_update_last_tick_id() -> None:
    store = EngineStatusStore()
    store.record_success("gossip", 4)
    store.record_error("gossip", 5, "boom")
    record = store.get("gossip")
    assert record is not None
    assert record.last_tick_id == 4


def test_error_count_increments() -> None:
    store = EngineStatusStore()
    store.record_error("gossip", 1, "err1")
    store.record_error("gossip", 2, "err2")
    record = store.get("gossip")
    assert record is not None
    assert record.error_count == 2


def test_success_does_not_increment_error_count() -> None:
    store = EngineStatusStore()
    store.record_error("gossip", 1, "err")
    store.record_success("gossip", 2)
    record = store.get("gossip")
    assert record is not None
    assert record.error_count == 1


def test_get_returns_none_for_unknown_engine() -> None:
    store = EngineStatusStore()
    assert store.get("unknown") is None


def test_get_all_returns_copy_not_reference() -> None:
    store = EngineStatusStore()
    store.record_success("gossip", 1)
    snapshot = store.get_all()
    snapshot["injected"] = EngineStatusRecord(engine_name="injected")
    assert "injected" not in store.get_all()


def test_multiple_engines_tracked_independently() -> None:
    store = EngineStatusStore()
    store.record_success("gossip", 10)
    store.record_error("event", 10, "event failure")
    assert store.get("gossip") is not None
    assert store.get("gossip").last_error is None
    assert store.get("event") is not None
    assert store.get("event").last_error == "event failure"
