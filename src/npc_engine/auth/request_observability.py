"""
request_observability.py - Request correlation-id, metrics, and structured logging helpers for ApiKeyMiddleware.
Layer: api
Purpose: Emit bounded-cardinality request logs/metrics and resolve correlation ids.
Does NOT: enforce auth, validate idempotency keys, or define the middleware class.
Dependencies injected: Settings (none directly; operates on Request/Response).
Used by: auth.middleware (ApiKeyMiddleware.dispatch).
"""

from time import perf_counter
import time

from fastapi import Request
from starlette.responses import Response

from npc_engine.utils.logging import get_logger
from npc_engine.utils.metrics import increment_metric, observe_metric, result_label_from_status


REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_FALLBACK_PREFIX = "req"

VALIDATION_FAILURES_METRIC = "validation_failures_total"
HTTP_REQUESTS_METRIC = "http_requests_total"
HTTP_REQUEST_LATENCY_METRIC = "http_request_latency_seconds"
REQUEST_COMPLETED_EVENT = "request_completed"

LOGGER = get_logger(__name__)


def _resolve_request_id(request: Request) -> str:
    """Resolve request correlation id from header or deterministic fallback.

    Args:
        request: Incoming FastAPI request.

    Returns:
        Correlation id string from X-Request-ID header or generated fallback.
    """
    header_value = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if header_value != "":
        return header_value
    return f"{REQUEST_ID_FALLBACK_PREFIX}:{request.method.lower()}:{time.time_ns()}"


def _record_request_observability(
    *,
    request: Request,
    request_id: str,
    route_label: str,
    status_code: int,
    started_at: float,
) -> None:
    """Emit bounded-cardinality request logs and metrics.

    Args:
        request: Incoming FastAPI request.
        request_id: Resolved request correlation id.
        route_label: Normalized route label for metric cardinality control.
        status_code: HTTP status code of the completed response.
        started_at: perf_counter timestamp captured at request start.
    """
    result = result_label_from_status(status_code=status_code)
    duration_seconds = perf_counter() - started_at
    labels = {
        "route": route_label,
        "method": request.method.lower(),
        "result": result,
    }
    increment_metric(metric=HTTP_REQUESTS_METRIC, labels=labels)
    observe_metric(metric=HTTP_REQUEST_LATENCY_METRIC, value=duration_seconds, labels=labels)
    LOGGER.info(
        REQUEST_COMPLETED_EVENT,
        extra={
            "request_id": request_id,
            "route": route_label,
            "method": request.method,
            "status_code": status_code,
            "result": result,
            "duration_ms": int(duration_seconds * 1000),
        },
    )


def _finalize_validation_failure_response(
    *,
    request: Request,
    request_id: str,
    route_label: str,
    started_at: float,
    response: Response,
    reason: str,
) -> Response:
    """Attach validation-failure metrics and observability for one response.

    Args:
        request: Incoming FastAPI request.
        request_id: Resolved request correlation id.
        route_label: Normalized route label for metric cardinality control.
        started_at: perf_counter timestamp captured at request start.
        response: Completed response object.
        reason: Machine-readable failure reason for metrics labeling.

    Returns:
        The same response with metrics and logs emitted.
    """
    increment_metric(
        metric=VALIDATION_FAILURES_METRIC,
        labels={"route": route_label, "reason": reason, "status": str(response.status_code)},
    )
    _record_request_observability(
        request=request,
        request_id=request_id,
        route_label=route_label,
        status_code=response.status_code,
        started_at=started_at,
    )
    return response
