"""
metrics.py - In-memory metrics registry and bounded label helpers for observability.
Layer: config
Purpose: (auto-detected — review)

Does NOT: export metrics to external backends.

Dependencies injected: None.
"""

from __future__ import annotations

from functools import lru_cache
from threading import Lock
from typing import Mapping


LABEL_MAX_LENGTH = 64
UNKNOWN_LABEL = "unknown"
NON_V1_ROUTE_LABEL = "non_v1"
HEALTH_ROUTE_LABEL = "health"
ROUTE_PREFIX_LABELS: tuple[tuple[str, str], ...] = (
    # admin surface — must be checked before bare "graph" to avoid mis-labelling
    ("admin/graph", "admin_graph"),
    ("admin/batch", "admin_batch"),
    ("admin/schema", "admin_schema"),
    ("admin", "admin"),
    # game-engine public surface
    ("graph", "graph"),
    ("ws/dialogue", "ws_dialogue"),
    ("dialogue", "dialogue"),
    ("action", "action"),
    ("quest", "quest"),
    ("clock", "clock"),
    ("npc", "npc_state"),
)


def _sanitize_label_value(value: str) -> str:
    """Normalize label values to bounded low-cardinality strings."""

    normalized = "".join(character if character.isalnum() or character in {"_", "-"} else "_" for character in value)
    normalized = normalized.lower().strip("_")
    if normalized == "":
        return UNKNOWN_LABEL
    return normalized[:LABEL_MAX_LENGTH]


def _normalize_labels(labels: Mapping[str, str] | None) -> tuple[tuple[str, str], ...]:
    """Convert label mapping to a deterministic tuple key."""

    if labels is None:
        return ()
    return tuple(sorted((str(key), _sanitize_label_value(str(value))) for key, value in labels.items()))


def route_label_from_path(path: str, api_v1_prefix: str) -> str:
    """Map raw request paths into bounded route labels."""

    if path == "/health":
        return HEALTH_ROUTE_LABEL
    if not path.startswith(api_v1_prefix):
        return NON_V1_ROUTE_LABEL

    suffix = path[len(api_v1_prefix) :].lstrip("/")
    if suffix == "":
        return "v1_root"

    for prefix, label in ROUTE_PREFIX_LABELS:
        if suffix.startswith(prefix):
            return label

    return _sanitize_label_value(suffix.split("/")[0])


def result_label_from_status(status_code: int) -> str:
    """Map status code into bounded result buckets."""

    if 200 <= status_code < 300:
        return "success"
    if 400 <= status_code < 500:
        return "client_error"
    if status_code >= 500:
        return "server_error"
    return "other"


class MetricsRegistry:
    """Thread-safe in-memory metrics registry for counters and observations."""

    def __init__(self) -> None:
        """Initialise empty counters and observations with a threading lock."""
        self._lock: Lock = Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._observations: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, float]] = {}

    def increment(self, metric: str, amount: float = 1.0, labels: Mapping[str, str] | None = None) -> None:
        """Increment a counter metric by amount."""

        key = (metric, _normalize_labels(labels))
        with self._lock:
            current = self._counters.get(key, 0.0)
            self._counters[key] = current + amount

    def observe(self, metric: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        """Record one observation for a sampled metric."""

        key = (metric, _normalize_labels(labels))
        with self._lock:
            current = self._observations.get(
                key,
                {
                    "count": 0.0,
                    "sum": 0.0,
                    "min": value,
                    "max": value,
                },
            )
            self._observations[key] = {
                "count": current["count"] + 1.0,
                "sum": current["sum"] + value,
                "min": min(current["min"], value),
                "max": max(current["max"], value),
            }

    def counter_value(self, metric: str, labels: Mapping[str, str] | None = None) -> float:
        """Return counter value for exact metric and labels."""

        key = (metric, _normalize_labels(labels))
        with self._lock:
            return self._counters.get(key, 0.0)

    def snapshot(self) -> dict[str, dict[str, float | dict[str, float]]]:
        """Return immutable snapshot of counters and observations."""

        with self._lock:
            return {
                "counters": {_serialize_key(key): value for key, value in self._counters.items()},
                "observations": {
                    _serialize_key(key): dict(values)
                    for key, values in self._observations.items()
                },
            }

    def reset(self) -> None:
        """Reset all in-memory metric state."""

        with self._lock:
            self._counters = {}
            self._observations = {}


def _serialize_key(key: tuple[str, tuple[tuple[str, str], ...]]) -> str:
    """Render a (metric, labels) key as a human-readable string for snapshots."""
    metric, labels = key
    if len(labels) == 0:
        return metric
    labels_segment = ",".join(f"{name}={value}" for name, value in labels)
    return f"{metric}|{labels_segment}"


@lru_cache
def get_metrics_registry() -> MetricsRegistry:
    """Return process-level singleton metrics registry."""

    return MetricsRegistry()


def increment_metric(metric: str, amount: float = 1.0, labels: Mapping[str, str] | None = None) -> None:
    """Increment metric in the default registry."""

    get_metrics_registry().increment(metric=metric, amount=amount, labels=labels)


def observe_metric(metric: str, value: float, labels: Mapping[str, str] | None = None) -> None:
    """Record observation in the default registry."""

    get_metrics_registry().observe(metric=metric, value=value, labels=labels)


def get_counter_value(metric: str, labels: Mapping[str, str] | None = None) -> float:
    """Get counter value from default registry for tests and diagnostics."""

    return get_metrics_registry().counter_value(metric=metric, labels=labels)


def reset_metrics_registry() -> None:
    """Reset default registry state for isolated test execution."""

    get_metrics_registry().reset()
