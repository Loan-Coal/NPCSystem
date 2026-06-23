"""
test_metrics.py - Unit tests for MetricsRegistry and label helpers.

Does NOT: connect to external metrics backends.
"""

from __future__ import annotations

import pytest

from npc_engine.utils.metrics import (
    HEALTH_ROUTE_LABEL,
    NON_V1_ROUTE_LABEL,
    MetricsRegistry,
    get_metrics_registry,
    reset_metrics_registry,
    result_label_from_status,
    route_label_from_path,
)


# ---------------------------------------------------------------------------
# result_label_from_status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [200, 201, 204, 299])
def test_result_label_2xx_is_success(code: int):
    assert result_label_from_status(code) == "success"


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422, 499])
def test_result_label_4xx_is_client_error(code: int):
    assert result_label_from_status(code) == "client_error"


@pytest.mark.parametrize("code", [500, 502, 503])
def test_result_label_5xx_is_server_error(code: int):
    assert result_label_from_status(code) == "server_error"


def test_result_label_other_status():
    assert result_label_from_status(301) == "other"


# ---------------------------------------------------------------------------
# route_label_from_path
# ---------------------------------------------------------------------------


def test_route_label_health_path():
    assert route_label_from_path("/health", "/v1") == HEALTH_ROUTE_LABEL


def test_route_label_non_v1_path():
    assert route_label_from_path("/admin-legacy/stuff", "/v1") == NON_V1_ROUTE_LABEL


def test_route_label_v1_root():
    assert route_label_from_path("/v1", "/v1") == "v1_root"


@pytest.mark.parametrize("path,expected", [
    ("/v1/graph/npc_1", "graph"),
    ("/v1/dialogue/session_1", "dialogue"),
    ("/v1/action/buy", "action"),
    ("/v1/quest/q_001", "quest"),
    ("/v1/clock/tick", "clock"),
    ("/v1/npc/state", "npc_state"),
    ("/v1/admin/graph/reindex", "admin_graph"),
    ("/v1/admin/batch/run", "admin_batch"),
    ("/v1/admin/schema/load", "admin_schema"),
    ("/v1/ws/dialogue/stream", "ws_dialogue"),
])
def test_route_label_known_prefixes(path: str, expected: str):
    assert route_label_from_path(path, "/v1") == expected


def test_route_label_unknown_v1_path_sanitized():
    label = route_label_from_path("/v1/schedules/sched_1", "/v1")
    assert label == "schedules"


# ---------------------------------------------------------------------------
# MetricsRegistry — increment / counter_value
# ---------------------------------------------------------------------------


def test_increment_and_read_counter():
    reg = MetricsRegistry()
    reg.increment("requests")
    assert reg.counter_value("requests") == 1.0


def test_increment_accumulates():
    reg = MetricsRegistry()
    reg.increment("requests", 3.0)
    reg.increment("requests", 2.0)
    assert reg.counter_value("requests") == 5.0


def test_counter_missing_key_returns_zero():
    reg = MetricsRegistry()
    assert reg.counter_value("nonexistent") == 0.0


def test_increment_with_labels_isolated():
    reg = MetricsRegistry()
    reg.increment("req", labels={"route": "graph"})
    reg.increment("req", labels={"route": "dialogue"})
    assert reg.counter_value("req", labels={"route": "graph"}) == 1.0
    assert reg.counter_value("req", labels={"route": "dialogue"}) == 1.0
    assert reg.counter_value("req") == 0.0


# ---------------------------------------------------------------------------
# MetricsRegistry — observe / snapshot
# ---------------------------------------------------------------------------


def test_observe_records_count_and_sum():
    reg = MetricsRegistry()
    reg.observe("latency", 0.1)
    reg.observe("latency", 0.3)
    snap = reg.snapshot()
    obs = snap["observations"]["latency"]
    assert obs["count"] == 2.0
    assert obs["sum"] == pytest.approx(0.4)


def test_observe_tracks_min_and_max():
    reg = MetricsRegistry()
    reg.observe("latency", 0.5)
    reg.observe("latency", 0.1)
    reg.observe("latency", 0.9)
    snap = reg.snapshot()
    obs = snap["observations"]["latency"]
    assert obs["min"] == pytest.approx(0.1)
    assert obs["max"] == pytest.approx(0.9)


def test_snapshot_contains_counters_and_observations():
    reg = MetricsRegistry()
    reg.increment("counter_metric")
    reg.observe("obs_metric", 1.0)
    snap = reg.snapshot()
    assert "counters" in snap
    assert "observations" in snap


# ---------------------------------------------------------------------------
# MetricsRegistry — reset
# ---------------------------------------------------------------------------


def test_reset_clears_counters():
    reg = MetricsRegistry()
    reg.increment("requests", 10.0)
    reg.reset()
    assert reg.counter_value("requests") == 0.0


def test_reset_clears_observations():
    reg = MetricsRegistry()
    reg.observe("latency", 1.0)
    reg.reset()
    snap = reg.snapshot()
    assert snap["observations"] == {}


# ---------------------------------------------------------------------------
# get_metrics_registry — singleton
# ---------------------------------------------------------------------------


def test_get_metrics_registry_returns_same_instance():
    r1 = get_metrics_registry()
    r2 = get_metrics_registry()
    assert r1 is r2


def test_reset_metrics_registry_helper():
    reset_metrics_registry()
    reg = get_metrics_registry()
    assert reg.counter_value("any_metric") == 0.0
