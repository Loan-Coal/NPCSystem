"""
graph_warning_helpers.py - Shared warning metadata and observability helpers for graph routes.
Layer: api
Purpose: (auto-detected — review)

Does NOT: execute graph operations.

Dependencies injected: None.
"""
from __future__ import annotations

from typing import Any

from npc_engine.utils.logging import get_logger
from npc_engine.utils.metrics import increment_metric


GRAPH_WARNINGS_METRIC = "graph_warnings_total"
GRAPH_WARNING_EVENT = "graph_warning"
GRAPH_ROUTE_LABEL = "graph"

LOGGER = get_logger(__name__)


def emit_graph_warnings(*, warnings: list[dict[str, Any]], request_id: str) -> None:
    """Emit warning metrics and structured logs for graph responses.

    Args:
        warnings: List of warning dicts from GenericGraphService.missing_extension_warnings.
        request_id: Resolved request correlation id for log correlation.
    """
    for warning in warnings:
        warning_code = str(warning.get("warning_code", "UNKNOWN_WARNING")).lower()
        increment_metric(
            metric=GRAPH_WARNINGS_METRIC,
            labels={"warning_code": warning_code, "route": GRAPH_ROUTE_LABEL},
        )
        LOGGER.warning(
            GRAPH_WARNING_EVENT,
            extra={
                "request_id": request_id,
                "warning_code": warning.get("warning_code", "UNKNOWN_WARNING"),
                "warning_type": warning.get("type", "unknown"),
                "warning_message": warning.get("message", ""),
                "node_type": warning.get("node_type", ""),
                "edge_type": warning.get("edge_type", ""),
                "field_name": warning.get("field_name", ""),
            },
        )


def attach_warnings_meta(*, base_meta: dict[str, Any] | None, warnings: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Attach warning payload to response meta while preserving existing metadata keys.

    Args:
        base_meta: Existing meta dict to extend, or None.
        warnings: List of warning dicts to embed under the "warnings" key.

    Returns:
        Updated meta dict with warnings attached, or None when warnings is empty and base_meta is None.
    """
    if len(warnings) == 0:
        return base_meta
    payload: dict[str, Any] = {} if base_meta is None else dict(base_meta)
    payload["warnings"] = warnings
    return payload
