"""
middleware_helpers.py - Standalone helper functions and shared constants for ApiKeyMiddleware.

Does NOT: define the middleware class itself.

Dependencies injected: Settings.
"""

from time import perf_counter
import time
from uuid import UUID

from fastapi import Request
from starlette.responses import JSONResponse, Response

from npc_engine.auth.permissions import SCOPE_GRAPH_ADMIN, SCOPE_GRAPH_WRITE
from npc_engine.config import Settings
from npc_engine.engines.idempotency.models import IdempotencyPreflightResult
from npc_engine.utils.errors import IdempotencyKeyInvalidError, IdempotencyKeyRequiredError
from npc_engine.utils.logging import get_logger
from npc_engine.utils.metrics import increment_metric, observe_metric, result_label_from_status


HEALTH_PATH = "/health"
OPTIONS_METHOD = "OPTIONS"
REQUEST_ID_HEADER = "X-Request-ID"
UUID_VERSION_V4 = 4

HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_CONFLICT = 409
HTTP_STATUS_UNPROCESSABLE_ENTITY = 422

IDEMPOTENCY_REQUIRED_CODE = "IDEMPOTENCY_KEY_REQUIRED"
IDEMPOTENCY_INVALID_CODE = "IDEMPOTENCY_KEY_INVALID"
IDEMPOTENCY_CONFLICT_CODE = "IDEMPOTENCY_KEY_CONFLICT"
IDEMPOTENCY_IN_FLIGHT_CODE = "IDEMPOTENCY_IN_FLIGHT"

MUTATING_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})

VALIDATION_FAILURES_METRIC = "validation_failures_total"
HTTP_REQUESTS_METRIC = "http_requests_total"
HTTP_REQUEST_LATENCY_METRIC = "http_request_latency_seconds"
REQUEST_COMPLETED_EVENT = "request_completed"
REQUEST_ID_FALLBACK_PREFIX = "req"

LOGGER = get_logger(__name__)


def _required_scope_for_path(path: str, api_v1_prefix: str) -> str | None:
    """Return required scope for the given path, or None for auth-only paths.

    Args:
        path: Incoming request path.
        api_v1_prefix: Configured API v1 prefix string.

    Returns:
        Scope string required to access the path, or None when no scope check applies.
    """
    admin_prefix = f"{api_v1_prefix}/admin"
    graph_write_prefix = f"{api_v1_prefix}/graph"

    if path.startswith(admin_prefix):
        return SCOPE_GRAPH_ADMIN
    if path.startswith(graph_write_prefix):
        return SCOPE_GRAPH_WRITE
    return None


def _requires_idempotency_key(method: str, path: str, settings: Settings) -> bool:
    """Return True when idempotency header preflight applies to this request.

    Args:
        method: HTTP method string.
        path: Incoming request path.
        settings: Application settings.

    Returns:
        True when the request requires an idempotency key header.
    """
    if not settings.IDEMPOTENCY_ENFORCE_HEADER:
        return False
    if method == OPTIONS_METHOD:
        return False
    if method not in MUTATING_METHODS:
        return False

    api_prefix = settings.API_V1_PREFIX
    if path == api_prefix:
        return True
    return path.startswith(f"{api_prefix}/")


def _validate_idempotency_key(request: Request, settings: Settings) -> None:
    """Validate configured idempotency header as UUIDv4.

    Args:
        request: Incoming FastAPI request.
        settings: Application settings.

    Raises:
        IdempotencyKeyRequiredError: When the header is absent or blank.
        IdempotencyKeyInvalidError: When the value is not a valid UUIDv4.
    """
    header_name = settings.IDEMPOTENCY_HEADER_NAME
    raw_value = request.headers.get(header_name)
    if raw_value is None or not raw_value.strip():
        raise IdempotencyKeyRequiredError(header_name=header_name)

    candidate_value = raw_value.strip()
    try:
        parsed_value = UUID(candidate_value)
    except ValueError as error:
        raise IdempotencyKeyInvalidError(header_name=header_name, value=candidate_value) from error

    if parsed_value.version != UUID_VERSION_V4:
        raise IdempotencyKeyInvalidError(header_name=header_name, value=candidate_value)


def _idempotency_error_response(request: Request, error_code: str, message: str, status_code: int) -> JSONResponse:
    """Build a stable idempotency error response payload.

    Args:
        request: Incoming FastAPI request.
        error_code: Machine-readable idempotency error code.
        message: Human-readable error message.
        status_code: HTTP status code for the response.

    Returns:
        JSONResponse with idempotency error envelope.
    """
    request_id = request.headers.get(REQUEST_ID_HEADER, "")
    payload = {
        "success": False,
        "error": error_code,
        "message": message,
        "request_id": request_id,
    }
    return JSONResponse(status_code=status_code, content=payload)


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


def _build_idempotency_decision_response(
    *,
    request: Request,
    preflight_result: IdempotencyPreflightResult,
) -> Response | None:
    """Build response for idempotency preflight decisions that stop execution.

    Args:
        request: Incoming FastAPI request.
        preflight_result: Result from IdempotencyService.preflight.

    Returns:
        A Response to return immediately, or None when the request should proceed.
    """
    if preflight_result.decision == "proceed":
        return None

    if preflight_result.decision == "replay":
        return Response(
            content=preflight_result.response_body or "{}",
            status_code=preflight_result.response_status_code or 200,
            media_type="application/json",
        )

    if preflight_result.decision == "conflict":
        return _idempotency_error_response(
            request=request,
            error_code=IDEMPOTENCY_CONFLICT_CODE,
            message="Idempotency key already used for a different request.",
            status_code=HTTP_STATUS_CONFLICT,
        )

    return _idempotency_error_response(
        request=request,
        error_code=IDEMPOTENCY_IN_FLIGHT_CODE,
        message="Request is still being processed. Retry after pending_timeout_seconds.",
        status_code=HTTP_STATUS_CONFLICT,
    )


async def _materialize_response(response: Response) -> tuple[str, Response]:
    """Materialize response body so it can be persisted for idempotent replay.

    Args:
        response: Completed response object, potentially with a streaming body.

    Returns:
        Tuple of (body_string, replayable_response) where replayable_response has a
        materialized body suitable for storage and replay.
    """
    existing_body = getattr(response, "body", b"")
    if isinstance(existing_body, (bytes, bytearray)) and existing_body:
        return bytes(existing_body).decode("utf-8"), response

    if not hasattr(response, "body_iterator"):
        return "", response

    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunks.append(chunk)
        else:
            chunks.append(chunk.encode("utf-8"))
    body_bytes = b"".join(chunks)
    replayable_response = Response(
        content=body_bytes,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=response.background,
    )
    return body_bytes.decode("utf-8"), replayable_response
