"""
Module: service
Layer: engines
Purpose: Idempotency decision engine backed by a sessionless storage protocol.
         IdempotencyService delegates all Neo4j I/O to IdempotencyStoreProtocol whose
         concrete adapter (Neo4jIdempotencyRepository) owns its sessions (DEC-122 / SEV-24).
Does NOT: open Neo4j sessions, parse HTTP headers directly, or hold a GraphDB.
Dependencies injected: Settings + IdempotencyStoreProtocol (constructor).
Used by: api/auth/idempotency_middleware.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from npc_engine.config import Settings
from npc_engine.engines.idempotency.models import IdempotencyPreflightResult
from npc_engine.engines.idempotency.service_helpers import (
    create_pending_if_absent,
    evaluate_existing_record,
    request_hash as _request_hash,
    resource_scope as _resource_scope,
    response_hash as _response_hash,
)
from npc_engine.engines.idempotency.store_protocol import IdempotencyStoreProtocol


STATUS_SERVER_ERROR = 500


class IdempotencyServiceProtocol(Protocol):
    """Service protocol used by middleware for idempotency flow."""

    async def ensure_constraints(self) -> None: ...

    async def preflight(
        self,
        *,
        idempotency_key: str,
        method: str,
        path: str,
        query_string: str,
        body_bytes: bytes,
    ) -> IdempotencyPreflightResult: ...

    async def finalize(
        self,
        *,
        idempotency_key: str,
        method: str,
        path: str,
        request_hash: str,
        status_code: int,
        response_body: str,
    ) -> None: ...

    async def cleanup_expired(self) -> int: ...


class IdempotencyService:
    """Evaluates preflight and finalization behavior for idempotent requests.

    All Neo4j I/O is delegated to the injected IdempotencyStoreProtocol whose
    concrete implementation manages its own sessions (DEC-122).
    """

    def __init__(
        self,
        settings: Settings,
        store: IdempotencyStoreProtocol,
    ) -> None:
        """Initialise the service with configuration and a sessionless store.

        Args:
            settings: Application settings providing idempotency timeout and retention config.
            store: Sessionless persistence backend implementing IdempotencyStoreProtocol.
        """
        self._settings = settings
        self._store = store

    async def ensure_constraints(self) -> None:
        """Ensure the Neo4j uniqueness constraint on idempotency records exists."""
        await self._store.ensure_constraints()

    async def preflight(
        self,
        *,
        idempotency_key: str,
        method: str,
        path: str,
        query_string: str,
        body_bytes: bytes,
    ) -> IdempotencyPreflightResult:
        """Evaluate whether an incoming request should proceed, replay, or wait.

        Args:
            idempotency_key: Client-supplied idempotency key header value.
            method: HTTP method (e.g. "POST").
            path: Request path (e.g. "/api/dialogue").
            query_string: Raw query string, may be empty.
            body_bytes: Raw request body bytes used for hash comparison.

        Returns:
            IdempotencyPreflightResult with decision "proceed", "replay", "conflict",
            or "in_flight" and any stored response fields for replay decisions.
        """
        scope = _resource_scope(method=method, path=path)
        req_hash = _request_hash(method=method, path=path, query_string=query_string, body_bytes=body_bytes)
        now = datetime.now(timezone.utc)

        record = await self._store.get_record(
            idempotency_key=idempotency_key,
            resource_scope=scope,
        )
        if record is None:
            created = await create_pending_if_absent(
                store=self._store,
                idempotency_key=idempotency_key,
                resource_scope=scope,
                request_hash=req_hash,
                now=now,
                settings=self._settings,
            )
            if created:
                return IdempotencyPreflightResult(decision="proceed", request_hash=req_hash)
            record = await self._store.get_record(
                idempotency_key=idempotency_key,
                resource_scope=scope,
            )
            if record is None:
                return IdempotencyPreflightResult(decision="proceed", request_hash=req_hash)

        return await evaluate_existing_record(
            store=self._store,
            record=record,
            idempotency_key=idempotency_key,
            resource_scope=scope,
            request_hash=req_hash,
            now=now,
            settings=self._settings,
        )

    async def finalize(
        self,
        *,
        idempotency_key: str,
        method: str,
        path: str,
        request_hash: str,
        status_code: int,
        response_body: str,
    ) -> None:
        """Persist the final response for a completed or failed-terminal request.

        Server errors (5xx) are stored as failed_terminal; all other responses as completed.

        Args:
            idempotency_key: Client-supplied idempotency key header value.
            method: HTTP method of the original request.
            path: Request path of the original request.
            request_hash: SHA-256 hex digest computed during preflight.
            status_code: HTTP status code of the response.
            response_body: Serialised response body string.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        resp_hash = _response_hash(status_code=status_code, response_body=response_body)
        scope = _resource_scope(method=method, path=path)

        if status_code >= STATUS_SERVER_ERROR:
            await self._store.mark_failed_terminal(
                idempotency_key=idempotency_key,
                resource_scope=scope,
                request_hash=request_hash,
                status_code=status_code,
                response_body=response_body,
                response_hash=resp_hash,
                updated_at=now_iso,
            )
            return

        await self._store.mark_completed(
            idempotency_key=idempotency_key,
            resource_scope=scope,
            request_hash=request_hash,
            status_code=status_code,
            response_body=response_body,
            response_hash=resp_hash,
            updated_at=now_iso,
        )

    async def cleanup_expired(self) -> int:
        """Delete all expired idempotency records and return the count removed.

        Returns:
            Number of records deleted.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        return await self._store.delete_expired(now_iso=now_iso)
