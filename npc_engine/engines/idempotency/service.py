"""
service.py - Idempotency decision engine backed by persistent storage.

Does NOT: parse HTTP headers directly.

Dependencies injected: Settings, GraphDB, IdempotencyStoreProtocol.
"""

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any, AsyncContextManager, Protocol

from neo4j import AsyncSession

from config import Settings
from engines.idempotency.models import IdempotencyPreflightResult
from engines.idempotency.store_protocol import IdempotencyStoreProtocol


STATUS_SERVER_ERROR = 500


class GraphSessionProvider(Protocol):
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

    def __init__(self, settings: Settings, graph_db: GraphSessionProvider, store: IdempotencyStoreProtocol):
        self._settings = settings
        self._graph_db = graph_db
        self._store = store

    async def ensure_constraints(self) -> None:
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
        resource_scope = _resource_scope(method=method, path=path)
        request_hash = _request_hash(method=method, path=path, query_string=query_string, body_bytes=body_bytes)
        now = datetime.now(timezone.utc)
        async with self._graph_db.get_session() as session:
            record = await self._store.get_record(
                session=session,
                idempotency_key=idempotency_key,
                resource_scope=resource_scope,
            )
            if record is None:
                created = await _create_pending_if_absent(
                    store=self._store,
                    session=session,
                    idempotency_key=idempotency_key,
                    resource_scope=resource_scope,
                    request_hash=request_hash,
                    now=now,
                    settings=self._settings,
                )
                if created:
                    return IdempotencyPreflightResult(decision="proceed", request_hash=request_hash)
                record = await self._store.get_record(
                    session=session,
                    idempotency_key=idempotency_key,
                    resource_scope=resource_scope,
                )
                if record is None:
                    return IdempotencyPreflightResult(decision="proceed", request_hash=request_hash)

            return await _evaluate_existing_record(
                store=self._store,
                session=session,
                record=record,
                idempotency_key=idempotency_key,
                resource_scope=resource_scope,
                request_hash=request_hash,
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
        now_iso = datetime.now(timezone.utc).isoformat()
        response_hash = _response_hash(status_code=status_code, response_body=response_body)
        resource_scope = _resource_scope(method=method, path=path)

        async with self._graph_db.get_session() as session:
            if status_code >= STATUS_SERVER_ERROR:
                await self._store.mark_failed_terminal(
                    session=session,
                    idempotency_key=idempotency_key,
                    resource_scope=resource_scope,
                    request_hash=request_hash,
                    status_code=status_code,
                    response_body=response_body,
                    response_hash=response_hash,
                    updated_at=now_iso,
                )
                return

            await self._store.mark_completed(
                session=session,
                idempotency_key=idempotency_key,
                resource_scope=resource_scope,
                request_hash=request_hash,
                status_code=status_code,
                response_body=response_body,
                response_hash=response_hash,
                updated_at=now_iso,
            )

    async def cleanup_expired(self) -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self._graph_db.get_session() as session:
            return await self._store.delete_expired(session=session, now_iso=now_iso)


async def _create_pending(
    *,
    store: IdempotencyStoreProtocol,
    session: AsyncSession,
    idempotency_key: str,
    resource_scope: str,
    request_hash: str,
    now: datetime,
    settings: Settings,
) -> None:
    expires_at = now + timedelta(hours=settings.IDEMPOTENCY_RETENTION_HOURS)
    await store.upsert_pending(
        session=session,
        idempotency_key=idempotency_key,
        resource_scope=resource_scope,
        request_hash=request_hash,
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        pending_timeout_seconds=settings.IDEMPOTENCY_PENDING_TIMEOUT_SECONDS,
    )


async def _create_pending_if_absent(
    *,
    store: IdempotencyStoreProtocol,
    session: AsyncSession,
    idempotency_key: str,
    resource_scope: str,
    request_hash: str,
    now: datetime,
    settings: Settings,
) -> bool:
    expires_at = now + timedelta(hours=settings.IDEMPOTENCY_RETENTION_HOURS)
    return await store.create_pending_if_absent(
        session=session,
        idempotency_key=idempotency_key,
        resource_scope=resource_scope,
        request_hash=request_hash,
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        pending_timeout_seconds=settings.IDEMPOTENCY_PENDING_TIMEOUT_SECONDS,
    )


async def _evaluate_existing_record(
    *,
    store: IdempotencyStoreProtocol,
    session: AsyncSession,
    record,
    idempotency_key: str,
    resource_scope: str,
    request_hash: str,
    now: datetime,
    settings: Settings,
) -> IdempotencyPreflightResult:
    if record.request_hash != request_hash:
        return IdempotencyPreflightResult(decision="conflict", request_hash=request_hash)

    if record.status in {"completed", "failed_terminal"}:
        return IdempotencyPreflightResult(
            decision="replay",
            request_hash=request_hash,
            response_status_code=record.response_status_code,
            response_body=record.response_body,
        )

    if _is_pending_in_flight(
        record_created_at=record.created_at,
        timeout_seconds=record.pending_timeout_seconds,
        now=now,
    ):
        return IdempotencyPreflightResult(
            decision="in_flight",
            request_hash=request_hash,
        )

    await _create_pending(
        store=store,
        session=session,
        idempotency_key=idempotency_key,
        resource_scope=resource_scope,
        request_hash=request_hash,
        now=now,
        settings=settings,
    )
    return IdempotencyPreflightResult(decision="proceed", request_hash=request_hash)


def _is_pending_in_flight(*, record_created_at: str, timeout_seconds: int, now: datetime) -> bool:
    created_at = _parse_datetime(record_created_at)
    cutoff = created_at + timedelta(seconds=timeout_seconds)
    return now <= cutoff


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _resource_scope(*, method: str, path: str) -> str:
    return f"{method.upper()}:{path}"


def _request_hash(*, method: str, path: str, query_string: str, body_bytes: bytes) -> str:
    payload = b"|".join(
        [
            method.upper().encode("utf-8"),
            path.encode("utf-8"),
            query_string.encode("utf-8"),
            body_bytes,
        ]
    )
    return hashlib.sha256(payload).hexdigest()


def _response_hash(*, status_code: int, response_body: str) -> str:
    payload = f"{status_code}|{response_body}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
