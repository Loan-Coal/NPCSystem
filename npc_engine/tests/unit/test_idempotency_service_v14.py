"""
test_idempotency_service_v14.py - Unit tests for v1.4 idempotency service semantics.

Does NOT: use real Neo4j connections.

Dependencies injected: in-memory store and graph session stubs.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

from config import Settings
from engines.idempotency.models import IdempotencyRecord
from engines.idempotency.service import IdempotencyService


class _GraphDbSessionStub:
    @asynccontextmanager
    async def get_session(self):
        yield object()


class _StoreStub:
    def __init__(self):
        self.records: dict[tuple[str, str], IdempotencyRecord] = {}

    async def ensure_constraints(self, session) -> None:
        return None

    async def get_record(self, session, *, idempotency_key: str, resource_scope: str) -> IdempotencyRecord | None:
        return self.records.get((idempotency_key, resource_scope))

    async def create_pending_if_absent(
        self,
        session,
        *,
        idempotency_key: str,
        resource_scope: str,
        request_hash: str,
        created_at: str,
        expires_at: str,
        pending_timeout_seconds: int,
    ) -> bool:
        key = (idempotency_key, resource_scope)
        if key in self.records:
            return False
        await self.upsert_pending(
            session,
            idempotency_key=idempotency_key,
            resource_scope=resource_scope,
            request_hash=request_hash,
            created_at=created_at,
            expires_at=expires_at,
            pending_timeout_seconds=pending_timeout_seconds,
        )
        return True

    async def upsert_pending(
        self,
        session,
        *,
        idempotency_key: str,
        resource_scope: str,
        request_hash: str,
        created_at: str,
        expires_at: str,
        pending_timeout_seconds: int,
    ) -> IdempotencyRecord:
        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            resource_scope=resource_scope,
            request_hash=request_hash,
            status="pending",
            created_at=created_at,
            expires_at=expires_at,
            pending_timeout_seconds=pending_timeout_seconds,
            updated_at=created_at,
        )
        self.records[(idempotency_key, resource_scope)] = record
        return record

    async def mark_completed(
        self,
        session,
        *,
        idempotency_key: str,
        resource_scope: str,
        request_hash: str,
        status_code: int,
        response_body: str,
        response_hash: str,
        updated_at: str,
    ) -> None:
        key = (idempotency_key, resource_scope)
        record = self.records[key]
        self.records[key] = record.model_copy(
            update={
                "status": "completed",
                "response_status_code": status_code,
                "response_body": response_body,
                "response_hash": response_hash,
                "updated_at": updated_at,
            }
        )

    async def mark_failed_terminal(
        self,
        session,
        *,
        idempotency_key: str,
        resource_scope: str,
        request_hash: str,
        status_code: int,
        response_body: str,
        response_hash: str,
        updated_at: str,
    ) -> None:
        key = (idempotency_key, resource_scope)
        record = self.records[key]
        self.records[key] = record.model_copy(
            update={
                "status": "failed_terminal",
                "response_status_code": status_code,
                "response_body": response_body,
                "response_hash": response_hash,
                "updated_at": updated_at,
            }
        )

    async def delete_expired(self, session, *, now_iso: str) -> int:
        now = datetime.fromisoformat(now_iso)
        original_size = len(self.records)
        self.records = {
            key: value
            for key, value in self.records.items()
            if datetime.fromisoformat(value.expires_at) >= now
        }
        return original_size - len(self.records)


def _build_service(store: _StoreStub) -> IdempotencyService:
    return IdempotencyService(
        settings=Settings(
            API_KEY_SECRET="local_dev_secret_change_this_2026",
            IDEMPOTENCY_ENFORCE_HEADER=True,
            IDEMPOTENCY_PENDING_TIMEOUT_SECONDS=30,
            IDEMPOTENCY_RETENTION_HOURS=24,
        ),
        graph_db=_GraphDbSessionStub(),
        store=store,
    )


@pytest.mark.asyncio
async def test_preflight_creates_pending_for_new_request() -> None:
    store = _StoreStub()
    service = _build_service(store=store)

    result = await service.preflight(
        idempotency_key="01234567-89ab-4def-8123-456789abcdef",
        method="POST",
        path="/v1/dialogue",
        query_string="",
        body_bytes=b'{"x":1}',
    )

    assert result.decision == "proceed"
    assert len(store.records) == 1


@pytest.mark.asyncio
async def test_preflight_returns_replay_for_completed_same_request_hash() -> None:
    store = _StoreStub()
    service = _build_service(store=store)
    key = "01234567-89ab-4def-8123-456789abcdef"

    first = await service.preflight(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        query_string="",
        body_bytes=b'{"x":1}',
    )
    await service.finalize(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        request_hash=first.request_hash,
        status_code=200,
        response_body='{"ok":true}',
    )

    replay = await service.preflight(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        query_string="",
        body_bytes=b'{"x":1}',
    )

    assert replay.decision == "replay"
    assert replay.response_status_code == 200
    assert replay.response_body == '{"ok":true}'


@pytest.mark.asyncio
async def test_preflight_returns_conflict_for_same_key_different_hash() -> None:
    store = _StoreStub()
    service = _build_service(store=store)
    key = "01234567-89ab-4def-8123-456789abcdef"

    await service.preflight(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        query_string="",
        body_bytes=b'{"x":1}',
    )

    conflict = await service.preflight(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        query_string="",
        body_bytes=b'{"x":2}',
    )

    assert conflict.decision == "conflict"


@pytest.mark.asyncio
async def test_preflight_returns_in_flight_for_recent_pending_request() -> None:
    store = _StoreStub()
    service = _build_service(store=store)
    key = "01234567-89ab-4def-8123-456789abcdef"

    await service.preflight(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        query_string="",
        body_bytes=b'{"x":1}',
    )
    result = await service.preflight(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        query_string="",
        body_bytes=b'{"x":1}',
    )

    assert result.decision == "in_flight"


@pytest.mark.asyncio
async def test_preflight_overwrites_pending_when_timeout_expired() -> None:
    store = _StoreStub()
    service = _build_service(store=store)
    key = "01234567-89ab-4def-8123-456789abcdef"

    await service.preflight(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        query_string="",
        body_bytes=b'{"x":1}',
    )

    record_key = (key, "POST:/v1/dialogue")
    stale = store.records[record_key]
    stale_created_at = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    store.records[record_key] = stale.model_copy(update={"created_at": stale_created_at})

    result = await service.preflight(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        query_string="",
        body_bytes=b'{"x":1}',
    )

    assert result.decision == "proceed"


@pytest.mark.asyncio
async def test_finalize_marks_failed_terminal_for_server_errors() -> None:
    store = _StoreStub()
    service = _build_service(store=store)
    key = "01234567-89ab-4def-8123-456789abcdef"

    preflight = await service.preflight(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        query_string="",
        body_bytes=b'{"x":1}',
    )
    await service.finalize(
        idempotency_key=key,
        method="POST",
        path="/v1/dialogue",
        request_hash=preflight.request_hash,
        status_code=500,
        response_body='{"detail":"boom"}',
    )

    record = store.records[(key, "POST:/v1/dialogue")]
    assert record.status == "failed_terminal"


@pytest.mark.asyncio
async def test_cleanup_expired_returns_deleted_count() -> None:
    store = _StoreStub()
    service = _build_service(store=store)

    now = datetime.now(timezone.utc)
    store.records[("a", "POST:/v1/dialogue")] = IdempotencyRecord(
        idempotency_key="a",
        resource_scope="POST:/v1/dialogue",
        request_hash="hash-a",
        status="pending",
        created_at=(now - timedelta(hours=2)).isoformat(),
        expires_at=(now - timedelta(minutes=1)).isoformat(),
        pending_timeout_seconds=30,
    )
    store.records[("b", "POST:/v1/dialogue")] = IdempotencyRecord(
        idempotency_key="b",
        resource_scope="POST:/v1/dialogue",
        request_hash="hash-b",
        status="pending",
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=1)).isoformat(),
        pending_timeout_seconds=30,
    )

    deleted = await service.cleanup_expired()

    assert deleted == 1
    assert len(store.records) == 1
