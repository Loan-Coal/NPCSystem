"""
test_engine_tick_timer.py - Unit tests for EngineTickTimer.

Does NOT: run a real engine, touch Neo4j, or perform async I/O.
Dependencies injected: EngineStatusStore is constructed per test.
"""

from __future__ import annotations

from npc_engine.scheduler.engine_status_store import EngineStatusStore
from npc_engine.scheduler.engine_tick_timer import (
    ENGINE_TICK_DURATION_MS_METRIC,
    ENGINE_TICKS_TOTAL_METRIC,
    EngineTickTimer,
)
from npc_engine.utils.metrics import get_counter_value, get_metrics_registry, reset_metrics_registry


def test_a_recorded_success_carries_a_duration_and_one_tick() -> None:
    """The gap this closes: /v1/admin/system/engines could say an engine ran, never how long."""
    store = EngineStatusStore()
    EngineTickTimer(engine_name="gossip", tick_id=7, status_store=store).record_success()

    record = store.get("gossip")
    assert record is not None
    assert record.last_tick_id == 7
    assert record.last_duration_ms is not None
    assert record.last_duration_ms >= 0.0
    assert record.tick_count == 1


def test_a_recorded_error_carries_a_duration_and_counts_as_a_tick() -> None:
    """A tick that ran and raised still ran, so it is timed and counted."""
    store = EngineStatusStore()
    EngineTickTimer(engine_name="event", tick_id=3, status_store=store).record_error("boom")

    record = store.get("event")
    assert record is not None
    assert record.last_error == "boom"
    assert record.error_count == 1
    assert record.last_duration_ms is not None
    assert record.tick_count == 1


def test_tick_count_accumulates_across_successes_and_errors() -> None:
    store = EngineStatusStore()
    for tick in range(3):
        EngineTickTimer(engine_name="gossip", tick_id=tick, status_store=store).record_success()
    EngineTickTimer(engine_name="gossip", tick_id=3, status_store=store).record_error("boom")

    record = store.get("gossip")
    assert record is not None
    assert record.tick_count == 4
    assert record.error_count == 1


def test_the_timer_emits_a_labelled_counter_and_observation() -> None:
    reset_metrics_registry()
    EngineTickTimer(engine_name="gossip", tick_id=1, status_store=None).record_success()

    assert get_counter_value(ENGINE_TICKS_TOTAL_METRIC, {"engine": "gossip", "result": "success"}) == 1.0
    observations = get_metrics_registry().snapshot()["observations"]
    key = f"{ENGINE_TICK_DURATION_MS_METRIC}|engine=gossip"
    assert key in observations, f"missing {key} in {sorted(observations)}"
    assert observations[key]["count"] == 1.0
    reset_metrics_registry()


def test_a_timer_without_a_store_still_emits_metrics_and_does_not_raise() -> None:
    """The scheduler treats the status store as optional; metrics must not depend on it."""
    reset_metrics_registry()
    EngineTickTimer(engine_name="event", tick_id=1, status_store=None).record_error("boom")

    assert get_counter_value(ENGINE_TICKS_TOTAL_METRIC, {"engine": "event", "result": "error"}) == 1.0
    reset_metrics_registry()
