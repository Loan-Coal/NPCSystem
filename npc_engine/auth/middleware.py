"""
middleware.py - FastAPI middleware that enforces API key auth on protected routes.

Does NOT: execute route business logic.

Dependencies injected: Settings.
"""

from uuid import UUID
from time import perf_counter
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from auth.permissions import SCOPE_GRAPH_ADMIN, SCOPE_GRAPH_WRITE, has_scope
from auth.api_key import resolve_scope_from_authorization
from config import Settings
from engines.idempotency.models import IdempotencyPreflightResult
from engines.idempotency.service import IdempotencyServiceProtocol
from utils.errors import AuthError, IdempotencyKeyInvalidError, IdempotencyKeyRequiredError
from utils.logging import get_logger
from utils.metrics import increment_metric, observe_metric, result_label_from_status, route_label_from_path


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
    """Return required scope for the given path, or None for auth-only paths."""

    graph_admin_prefix = f"{api_v1_prefix}/graph/admin"
    graph_write_prefix = f"{api_v1_prefix}/graph"
    schema_path = f"{api_v1_prefix}/schema"

    if path.startswith(graph_admin_prefix):
        return SCOPE_GRAPH_ADMIN
    if path == schema_path:
        return None
    if path.startswith(graph_write_prefix):
        return SCOPE_GRAPH_WRITE
    return None


def _requires_idempotency_key(method: str, path: str, settings: Settings) -> bool:
    """Return True when idempotency header preflight applies to this request."""

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
    """Validate configured idempotency header as UUIDv4."""

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
    """Build a stable idempotency error response payload."""

    request_id = request.headers.get(REQUEST_ID_HEADER, "")
    payload = {
        "success": False,
        "error": error_code,
        "message": message,
        "request_id": request_id,
    }
    return JSONResponse(status_code=status_code, content=payload)


def _resolve_request_id(request: Request) -> str:
    """Resolve request correlation id from header or deterministic fallback."""

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
    """Emit bounded-cardinality request logs and metrics."""

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


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Enforce Bearer auth for all routes except health."""

    def __init__(
        self,
        app,
        settings: Settings,
        idempotency_service: IdempotencyServiceProtocol | None = None,
    ):
        super().__init__(app)
        self._settings = settings
        self._idempotency_service = idempotency_service

    async def dispatch(self, request: Request, call_next):
        """Validate auth header before forwarding request."""

        request_id = _resolve_request_id(request=request)
        request.state.request_id = request_id
        route_label = route_label_from_path(path=request.url.path, api_v1_prefix=self._settings.API_V1_PREFIX)
        started_at = perf_counter()

        if request.url.path == HEALTH_PATH:
            try:
                response = await call_next(request)
            except Exception:
                _record_request_observability(
                    request=request,
                    request_id=request_id,
                    route_label=route_label,
                    status_code=500,
                    started_at=started_at,
                )
                raise
            _record_request_observability(
                request=request,
                request_id=request_id,
                route_label=route_label,
                status_code=response.status_code,
                started_at=started_at,
            )
            return response

        authorization = request.headers.get("Authorization", "")
        try:
            granted_scope = resolve_scope_from_authorization(
                authorization=authorization,
                settings=self._settings,
            )
            required_scope = _required_scope_for_path(
                path=request.url.path,
                api_v1_prefix=self._settings.API_V1_PREFIX,
            )
            if required_scope and not has_scope(granted_scope=granted_scope, required_scope=required_scope):
                response = JSONResponse(status_code=HTTP_STATUS_FORBIDDEN, content={"detail": "Forbidden"})
                increment_metric(
                    metric=VALIDATION_FAILURES_METRIC,
                    labels={"route": route_label, "reason": "forbidden", "status": str(HTTP_STATUS_FORBIDDEN)},
                )
                _record_request_observability(
                    request=request,
                    request_id=request_id,
                    route_label=route_label,
                    status_code=response.status_code,
                    started_at=started_at,
                )
                return response
            request.state.api_scope = granted_scope
        except AuthError:
            response = JSONResponse(status_code=HTTP_STATUS_UNAUTHORIZED, content={"detail": "Unauthorized"})
            increment_metric(
                metric=VALIDATION_FAILURES_METRIC,
                labels={"route": route_label, "reason": "unauthorized", "status": str(HTTP_STATUS_UNAUTHORIZED)},
            )
            _record_request_observability(
                request=request,
                request_id=request_id,
                route_label=route_label,
                status_code=response.status_code,
                started_at=started_at,
            )
            return response

        idempotency_key = ""
        preflight_result: IdempotencyPreflightResult | None = None

        if _requires_idempotency_key(method=request.method, path=request.url.path, settings=self._settings):
            try:
                _validate_idempotency_key(request=request, settings=self._settings)
            except IdempotencyKeyRequiredError:
                response = _idempotency_error_response(
                    request=request,
                    error_code=IDEMPOTENCY_REQUIRED_CODE,
                    message=f"{self._settings.IDEMPOTENCY_HEADER_NAME} header is required.",
                    status_code=HTTP_STATUS_BAD_REQUEST,
                )
                increment_metric(
                    metric=VALIDATION_FAILURES_METRIC,
                    labels={"route": route_label, "reason": IDEMPOTENCY_REQUIRED_CODE.lower(), "status": str(response.status_code)},
                )
                _record_request_observability(
                    request=request,
                    request_id=request_id,
                    route_label=route_label,
                    status_code=response.status_code,
                    started_at=started_at,
                )
                return response
            except IdempotencyKeyInvalidError:
                response = _idempotency_error_response(
                    request=request,
                    error_code=IDEMPOTENCY_INVALID_CODE,
                    message=f"{self._settings.IDEMPOTENCY_HEADER_NAME} must be a valid UUIDv4.",
                    status_code=HTTP_STATUS_UNPROCESSABLE_ENTITY,
                )
                increment_metric(
                    metric=VALIDATION_FAILURES_METRIC,
                    labels={"route": route_label, "reason": IDEMPOTENCY_INVALID_CODE.lower(), "status": str(response.status_code)},
                )
                _record_request_observability(
                    request=request,
                    request_id=request_id,
                    route_label=route_label,
                    status_code=response.status_code,
                    started_at=started_at,
                )
                return response

            idempotency_key = request.headers.get(self._settings.IDEMPOTENCY_HEADER_NAME, "").strip()
            request.state.idempotency_key = idempotency_key

            if self._idempotency_service is not None:
                body_bytes = await request.body()
                preflight_result = await self._idempotency_service.preflight(
                    idempotency_key=idempotency_key,
                    method=request.method,
                    path=request.url.path,
                    query_string=request.url.query,
                    body_bytes=body_bytes,
                )
                request.state.idempotency_request_hash = preflight_result.request_hash
                replay_response = _build_idempotency_decision_response(
                    request=request,
                    preflight_result=preflight_result,
                )
                if replay_response is not None:
                    if preflight_result.decision in {"conflict", "in_flight"}:
                        increment_metric(
                            metric=VALIDATION_FAILURES_METRIC,
                            labels={
                                "route": route_label,
                                "reason": f"idempotency_{preflight_result.decision}",
                                "status": str(replay_response.status_code),
                            },
                        )
                    _record_request_observability(
                        request=request,
                        request_id=request_id,
                        route_label=route_label,
                        status_code=replay_response.status_code,
                        started_at=started_at,
                    )
                    return replay_response

        try:
            response = await call_next(request)

            if preflight_result is None or preflight_result.decision != "proceed":
                _record_request_observability(
                    request=request,
                    request_id=request_id,
                    route_label=route_label,
                    status_code=response.status_code,
                    started_at=started_at,
                )
                return response

            if self._idempotency_service is None:
                _record_request_observability(
                    request=request,
                    request_id=request_id,
                    route_label=route_label,
                    status_code=response.status_code,
                    started_at=started_at,
                )
                return response

            response_body, replayable_response = await _materialize_response(response=response)
            await self._idempotency_service.finalize(
                idempotency_key=idempotency_key,
                method=request.method,
                path=request.url.path,
                request_hash=preflight_result.request_hash,
                status_code=replayable_response.status_code,
                response_body=response_body,
            )

            _record_request_observability(
                request=request,
                request_id=request_id,
                route_label=route_label,
                status_code=replayable_response.status_code,
                started_at=started_at,
            )
            return replayable_response
        except Exception:
            _record_request_observability(
                request=request,
                request_id=request_id,
                route_label=route_label,
                status_code=500,
                started_at=started_at,
            )
            raise


def _build_idempotency_decision_response(
    *,
    request: Request,
    preflight_result: IdempotencyPreflightResult,
) -> Response | None:
    """Build response for idempotency preflight decisions that stop execution."""

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
    """Materialize response body so it can be persisted for idempotent replay."""

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
