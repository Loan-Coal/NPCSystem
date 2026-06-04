"""
service.py - Idempotency decision engine backed by persistent storage.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: parse HTTP headers directly.

Dependencies injected: Settings, GraphDB, IdempotencyStoreProtocol.
"""

from datetime import datetime, timezone
from typing import Any, AsyncContextManager, Protocol

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


class GraphSessionProvider(Protocol):
    """Protocol for objects that expose a Neo4j session context manager."""

    def get_session(self) -> AsyncContextManager[Any]: ...


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
    """Evaluates preflight and finalization behavior for idempotent requests."""

    def __init__(
        self,
        settings: Settings,
        graph_db: GraphSessionProvider,
        store: IdempotencyStoreProtocol,
    ) -> None:
        """Initialise the service with configuration and persistence dependencies.

        Args:
            settings: Application settings providing idempotency timeout and retention config.
            graph_db: Provider for Neo4j session context managers.
            store: Persistence backend implementing IdempotencyStoreProtocol.
        """
        self._settings = settings
        self._graph_db = graph_db
        self._store = store

    async def ensure_constraints(self) -> None:
        """Ensure the Neo4j uniqueness constraint on idempotency records exists."""
        async with self._graph_db.get_session() as session:
            await self._store.ensure_constraints(session=session)

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
        async with self._graph_db.get_session() as session:
            record = await self._store.get_record(
                session=session,
                idempotency_key=idempotency_key,
                resource_scope=scope,
            )
            if record is None:
                created = await create_pending_if_absent(
                    store=self._store,
                    session=session,
                    idempotency_key=idempotency_key,
                    resource_scope=scope,
                    request_hash=req_hash,
                    now=now,
                    settings=self._settings,
                )
                if created:
                    return IdempotencyPreflightResult(decision="proceed", request_hash=req_hash)
                record = await self._store.get_record(
                    session=session,
                    idempotency_key=idempotency_key,
                    resource_scope=scope,
                )
                if record is None:
                    return IdempotencyPreflightResult(decision="proceed", request_hash=req_hash)

            return await evaluate_existing_record(
                store=self._store,
                session=session,
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

        async with self._graph_db.get_session() as session:
            if status_code >= STATUS_SERVER_ERROR:
                await self._store.mark_failed_terminal(
                    session=session,
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
                session=session,
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
        async with self._graph_db.get_session() as session:
            return await self._store.delete_expired(session=session, now_iso=now_iso)
