"""
middleware.py - FastAPI middleware that enforces API key auth on protected routes.
Layer: api
Purpose: FastAPI middleware that enforces API key auth on protected routes.

Does NOT: execute route business logic.

Dependencies injected: Settings.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from npc_engine.auth.api_key import resolve_scope_from_authorization
from npc_engine.api.errors import ErrorBody, ErrorEnvelope
from npc_engine.auth.middleware_helpers import (
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_FORBIDDEN,
    HTTP_STATUS_UNAUTHORIZED,
    HTTP_STATUS_UNPROCESSABLE_ENTITY,
    IDEMPOTENCY_INVALID_CODE,
    IDEMPOTENCY_REQUIRED_CODE,
    _build_idempotency_decision_response,
    _idempotency_error_response,
    _materialize_response,
    _required_scope_for_path,
    _requires_idempotency_key,
    _validate_idempotency_key,
    is_public_path,
)
from npc_engine.auth.request_observability import (
    _finalize_validation_failure_response,
    _record_request_observability,
    _resolve_request_id,
)
from npc_engine.auth.permissions import has_scope
from npc_engine.config import Settings
from npc_engine.engines.idempotency.models import IdempotencyPreflightResult
from npc_engine.engines.idempotency.service import IdempotencyServiceProtocol
from npc_engine.utils.errors import AuthError, IdempotencyKeyInvalidError, IdempotencyKeyRequiredError
from npc_engine.utils.metrics import route_label_from_path


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Enforce Bearer auth for all routes except health."""

    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        idempotency_service: IdempotencyServiceProtocol | None = None,
    ) -> None:
        """Initialize middleware with settings and optional idempotency service.

        Args:
            app: ASGI application to wrap.
            settings: Application settings used for auth and idempotency configuration.
            idempotency_service: Optional idempotency service for preflight and finalization.
        """
        super().__init__(app)
        self._settings = settings
        self._idempotency_service = idempotency_service

    async def _handle_public_path(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]],
        request_id: str, route_label: str, started_at: float,
    ) -> Response:
        """Forward a public (unauthenticated) path and record observability."""
        try:
            response = await call_next(request)
        except Exception:
            _record_request_observability(request=request, request_id=request_id, route_label=route_label, status_code=500, started_at=started_at)
            raise
        _record_request_observability(request=request, request_id=request_id, route_label=route_label, status_code=response.status_code, started_at=started_at)
        return response

    def _validate_auth(
        self, request: Request, request_id: str, route_label: str, started_at: float,
    ) -> Response | str:
        """Resolve scope from Authorization header; return granted_scope or error Response."""
        authorization = request.headers.get("Authorization", "")
        try:
            granted_scope = resolve_scope_from_authorization(authorization=authorization, settings=self._settings)
            required_scope = _required_scope_for_path(path=request.url.path, api_v1_prefix=self._settings.API_V1_PREFIX)
            if required_scope and not has_scope(granted_scope=granted_scope, required_scope=required_scope):
                return _finalize_validation_failure_response(
                    request=request, request_id=request_id, route_label=route_label, started_at=started_at,
                    response=JSONResponse(status_code=HTTP_STATUS_FORBIDDEN, content=ErrorEnvelope(error=ErrorBody(code="http_403", message="Forbidden")).model_dump()),
                    reason="forbidden",
                )
            return granted_scope
        except AuthError:
            return _finalize_validation_failure_response(
                request=request, request_id=request_id, route_label=route_label, started_at=started_at,
                response=JSONResponse(status_code=HTTP_STATUS_UNAUTHORIZED, content=ErrorEnvelope(error=ErrorBody(code="http_401", message="Unauthorized")).model_dump()),
                reason="unauthorized",
            )

    def _validate_idempotency_header(
        self, request: Request, request_id: str, route_label: str, started_at: float,
    ) -> tuple[str, Response | None]:
        """Validate idempotency header if required; return (key, None) or ('', error_response)."""
        if not _requires_idempotency_key(method=request.method, path=request.url.path, settings=self._settings):
            return "", None
        try:
            _validate_idempotency_key(request=request, settings=self._settings)
        except IdempotencyKeyRequiredError:
            return "", _finalize_validation_failure_response(
                request=request, request_id=request_id, route_label=route_label, started_at=started_at,
                response=_idempotency_error_response(request=request, error_code=IDEMPOTENCY_REQUIRED_CODE, message=f"{self._settings.IDEMPOTENCY_HEADER_NAME} header is required.", status_code=HTTP_STATUS_BAD_REQUEST),
                reason=IDEMPOTENCY_REQUIRED_CODE.lower(),
            )
        except IdempotencyKeyInvalidError:
            return "", _finalize_validation_failure_response(
                request=request, request_id=request_id, route_label=route_label, started_at=started_at,
                response=_idempotency_error_response(request=request, error_code=IDEMPOTENCY_INVALID_CODE, message=f"{self._settings.IDEMPOTENCY_HEADER_NAME} must be a valid UUIDv4.", status_code=HTTP_STATUS_UNPROCESSABLE_ENTITY),
                reason=IDEMPOTENCY_INVALID_CODE.lower(),
            )
        idempotency_key = request.headers.get(self._settings.IDEMPOTENCY_HEADER_NAME, "").strip()
        request.state.idempotency_key = idempotency_key
        return idempotency_key, None

    async def _run_idempotency_preflight(
        self, request: Request, idempotency_key: str, request_id: str, route_label: str, started_at: float,
    ) -> tuple[IdempotencyPreflightResult | None, Response | None]:
        """Run idempotency preflight if service and key are present; return (result, replay_or_None)."""
        if not idempotency_key or self._idempotency_service is None:
            return None, None
        body_bytes = await request.body()
        preflight_result = await self._idempotency_service.preflight(
            idempotency_key=idempotency_key, method=request.method,
            path=request.url.path, query_string=request.url.query, body_bytes=body_bytes,
        )
        request.state.idempotency_request_hash = preflight_result.request_hash
        replay_response = _build_idempotency_decision_response(request=request, preflight_result=preflight_result)
        if replay_response is None:
            return preflight_result, None
        if preflight_result.decision in {"conflict", "in_flight"}:
            return preflight_result, _finalize_validation_failure_response(
                request=request, request_id=request_id, route_label=route_label, started_at=started_at,
                response=replay_response, reason=f"idempotency_{preflight_result.decision}",
            )
        _record_request_observability(request=request, request_id=request_id, route_label=route_label, status_code=replay_response.status_code, started_at=started_at)
        return preflight_result, replay_response

    async def _execute_and_record(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]],
        idempotency_key: str, preflight_result: IdempotencyPreflightResult | None,
        request_id: str, route_label: str, started_at: float,
    ) -> Response:
        """Forward request, optionally finalize idempotency, and record observability."""
        try:
            response = await call_next(request)
            if preflight_result is None or preflight_result.decision != "proceed" or self._idempotency_service is None:
                _record_request_observability(request=request, request_id=request_id, route_label=route_label, status_code=response.status_code, started_at=started_at)
                return response
            response_body, replayable_response = await _materialize_response(response=response)
            await self._idempotency_service.finalize(
                idempotency_key=idempotency_key, method=request.method, path=request.url.path,
                request_hash=preflight_result.request_hash, status_code=replayable_response.status_code, response_body=response_body,
            )
            _record_request_observability(request=request, request_id=request_id, route_label=route_label, status_code=replayable_response.status_code, started_at=started_at)
            return replayable_response
        except Exception:
            _record_request_observability(request=request, request_id=request_id, route_label=route_label, status_code=500, started_at=started_at)
            raise

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Validate auth and idempotency, forward request, record observability.

        Args:
            request: Incoming FastAPI request.
            call_next: ASGI callable forwarding the request to the route handler.

        Returns:
            Response from the route handler or an error response.
        """
        request_id = _resolve_request_id(request=request)
        request.state.request_id = request_id
        route_label = route_label_from_path(path=request.url.path, api_v1_prefix=self._settings.API_V1_PREFIX)
        started_at = perf_counter()
        if is_public_path(request.url.path, env=self._settings.ENV):
            return await self._handle_public_path(request, call_next, request_id, route_label, started_at)
        auth_response = self._validate_auth(request, request_id, route_label, started_at)
        if isinstance(auth_response, Response):
            return auth_response
        request.state.api_scope = auth_response
        idempotency_key, key_error = self._validate_idempotency_header(request, request_id, route_label, started_at)
        if key_error is not None:
            return key_error
        preflight_result, replay_response = await self._run_idempotency_preflight(request, idempotency_key, request_id, route_label, started_at)
        if replay_response is not None:
            return replay_response
        return await self._execute_and_record(request, call_next, idempotency_key, preflight_result, request_id, route_label, started_at)
