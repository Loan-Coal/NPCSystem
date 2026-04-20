"""
test_metrics_observability_v14.py - Unit tests for bounded metrics helper behavior.

Does NOT: call external observability backends.

Dependencies injected: None.
"""

from utils.metrics import (
    get_counter_value,
    get_metrics_registry,
    increment_metric,
    observe_metric,
    reset_metrics_registry,
    result_label_from_status,
    route_label_from_path,
)
from typing import cast


def setup_function() -> None:
    reset_metrics_registry()


def test_metrics_registry_increments_and_snapshots_counters() -> None:
    """Counter metrics should be deterministic across repeated increments."""

    increment_metric("graph_writes_total", labels={"operation": "relation_delta", "result": "success"})
    increment_metric("graph_writes_total", labels={"operation": "relation_delta", "result": "success"})

    value = get_counter_value("graph_writes_total", labels={"operation": "relation_delta", "result": "success"})
    snapshot = get_metrics_registry().snapshot()

    assert value == 2.0
    assert snapshot["counters"]["graph_writes_total|operation=relation_delta,result=success"] == 2.0


def test_route_label_mapping_is_bounded_for_known_routes() -> None:
    """Route labels should map dynamic paths into bounded categories."""

    assert route_label_from_path("/v1/dialogue", "/v1") == "dialogue"
    assert route_label_from_path("/v1/graph/nodes/character/abc", "/v1") == "graph"
    assert route_label_from_path("/v1/graph/admin/reindex", "/v1") == "graph_admin"
    assert route_label_from_path("/v99/dialogue", "/v1") == "non_v1"


def test_result_label_mapping_buckets_status_codes() -> None:
    """Status labels should remain in bounded result buckets."""

    assert result_label_from_status(200) == "success"
    assert result_label_from_status(422) == "client_error"
    assert result_label_from_status(503) == "server_error"


def test_observations_snapshot_uses_bounded_aggregates() -> None:
    """Observation metrics should track bounded aggregate values, not raw samples."""

    observe_metric("http_request_latency_seconds", value=0.1, labels={"route": "dialogue"})
    observe_metric("http_request_latency_seconds", value=0.3, labels={"route": "dialogue"})

    snapshot = get_metrics_registry().snapshot()
    aggregate = cast(
        dict[str, float],
        snapshot["observations"]["http_request_latency_seconds|route=dialogue"],
    )

    assert aggregate["count"] == 2.0
    assert abs(aggregate["sum"] - 0.4) < 1e-9
    assert aggregate["min"] == 0.1
    assert aggregate["max"] == 0.3
