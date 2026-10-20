"""
Module: test_engine_status_working_set
Purpose: T15.1 RED anchor — working_set_size on EngineStatusRecord.
Asserts an engine returning a zero-size working set is distinguishable
from one that did work.
Does NOT: touch Neo4j, start a server, or perform I/O.
"""

from __future__ import annotations

import pytest

pytest.importorskip("neo4j")

from npc_engine.scheduler.engine_status_store import EngineStatusRecord, EngineStatusStore


def test_zero_working_set_is_distinguishable_from_nonzero() -> None:
    """Engine that did no work must have a different working_set_size than one that did."""
    store = EngineStatusStore()
    store.record_success("idle_engine", tick_id=1, working_set_size=0)
    store.record_success("active_engine", tick_id=1, working_set_size=5)

    idle = store.get("idle_engine")
    active = store.get("active_engine")

    assert idle is not None
    assert active is not None
    assert idle.working_set_size == 0
    assert active.working_set_size == 5
    assert idle.working_set_size != active.working_set_size


def test_working_set_size_defaults_to_none() -> None:
    """Records without a working_set_size argument default to None (pre-feature compat)."""
    store = EngineStatusStore()
    store.record_success("engine", tick_id=1)

    record = store.get("engine")

    assert record is not None
    assert record.working_set_size is None


def test_working_set_size_field_on_record() -> None:
    """EngineStatusRecord accepts working_set_size at construction time."""
    record = EngineStatusRecord(engine_name="test", working_set_size=7)

    assert record.working_set_size == 7
