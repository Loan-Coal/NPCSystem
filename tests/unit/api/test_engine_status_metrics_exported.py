"""
Module: test_engine_status_metrics_exported
Purpose: T15.1 RED anchor — engine_error_count and engine_working_set_size gauges
on GET /v1/system/metrics.
Asserts a non-null last_error produces a non-zero engine_error_count gauge in the
snapshot, and that working_set_size is also reflected.
Does NOT: touch Neo4j, start a server with lifespan, or perform I/O.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

pytest.importorskip("neo4j")

from npc_engine.api.routes.admin.system import v1_router
from npc_engine.scheduler.engine_status_store import EngineStatusStore
from npc_engine.utils.metrics import reset_metrics_registry


def _metrics_app() -> FastAPI:
    app = FastAPI()
    app.include_router(v1_router, prefix="/v1")
    return app


def test_engine_error_count_gauge_present_after_error() -> None:
    """A record_error call must produce engine_error_count gauge in metrics snapshot."""
    reset_metrics_registry()

    store = EngineStatusStore()
    store.record_error("gossip", tick_id=5, error="boom")

    client = TestClient(_metrics_app())
    response = client.get("/v1/system/metrics")
    payload = response.json()

    assert response.status_code == 200
    gauges = payload["data"].get("gauges", {})
    assert "engine_error_count|engine=gossip" in gauges, (
        f"expected engine_error_count gauge for gossip; got keys: {list(gauges)}"
    )
    assert gauges["engine_error_count|engine=gossip"] == 1.0

    reset_metrics_registry()


def test_engine_last_error_tick_gauge_present_after_error() -> None:
    """record_error must set engine_last_error_tick gauge to the tick it occurred on."""
    reset_metrics_registry()

    store = EngineStatusStore()
    store.record_error("event", tick_id=12, error="oops")

    client = TestClient(_metrics_app())
    response = client.get("/v1/system/metrics")
    payload = response.json()

    assert response.status_code == 200
    gauges = payload["data"].get("gauges", {})
    assert "engine_last_error_tick|engine=event" in gauges, (
        f"expected engine_last_error_tick gauge for event; got keys: {list(gauges)}"
    )
    assert gauges["engine_last_error_tick|engine=event"] == 12.0

    reset_metrics_registry()


def test_engine_working_set_size_gauge_present_after_success() -> None:
    """record_success with working_set_size must set the gauge in metrics snapshot."""
    reset_metrics_registry()

    store = EngineStatusStore()
    store.record_success("routine", tick_id=3, working_set_size=7)

    client = TestClient(_metrics_app())
    response = client.get("/v1/system/metrics")
    payload = response.json()

    assert response.status_code == 200
    gauges = payload["data"].get("gauges", {})
    assert "engine_working_set_size|engine=routine" in gauges, (
        f"expected engine_working_set_size gauge for routine; got keys: {list(gauges)}"
    )
    assert gauges["engine_working_set_size|engine=routine"] == 7.0

    reset_metrics_registry()
