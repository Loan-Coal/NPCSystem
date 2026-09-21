"""
test_idempotency_repository_integration.py — Integration tests for Neo4jIdempotencyRepository.

Covers the 7 public methods that T11.2 identified as having no unit-or-integration path:
ensure_constraints, get_record, create_pending_if_absent, upsert_pending, mark_completed,
mark_failed_terminal, delete_expired.

Does NOT: test IdempotencyService business logic (replay, conflict).

Dependencies injected: eval-stack Neo4j via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from npc_engine.config import Settings
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.repositories.idempotency_repository import Neo4jIdempotencyRepository


def _make_repo() -> Neo4jIdempotencyRepository:
    """Build a repository wired to the eval-stack Neo4j, or skip if env vars are absent."""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    settings = Settings(
        API_KEY_SECRET="local_dev_secret_change_this_2026",
        NEO4J_URI=uri,
        NEO4J_USER=user,
        NEO4J_PASSWORD=password,
    )
    return Neo4jIdempotencyRepository(GraphDB(settings))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _future_iso(seconds: int = 3600) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _past_iso(seconds: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


@pytest.mark.asyncio
async def test_ensure_constraints_is_idempotent() -> None:
    """ensure_constraints can be called twice without corrupting existing constraints."""
    repo = _make_repo()
    try:
        await repo.ensure_constraints()
        record_before = await repo.get_record("test-ensure-constraints-idempotency-probe")
        await repo.ensure_constraints()
        record_after = await repo.get_record("test-ensure-constraints-idempotency-probe")
    finally:
        await repo._graph_db.close()
    assert record_before == record_after


@pytest.mark.asyncio
async def test_get_record_returns_none_when_absent() -> None:
    """get_record returns None for a key that was never created."""
    repo = _make_repo()
    try:
        result = await repo.get_record(
            idempotency_key=f"key-{uuid4()}",
            resource_scope="GET /test",
        )
        assert result is None
    finally:
        await repo._graph_db.close()


@pytest.mark.asyncio
async def test_create_pending_if_absent_returns_true_then_false() -> None:
    """create_pending_if_absent: True on first call, False on duplicate key."""
    repo = _make_repo()
    key = f"key-{uuid4()}"
    scope = "POST /items"
    try:
        created = await repo.create_pending_if_absent(
            idempotency_key=key,
            resource_scope=scope,
            request_hash="abc123",
            created_at=_now_iso(),
            expires_at=_future_iso(),
            pending_timeout_seconds=30,
        )
        assert created is True

        duplicate = await repo.create_pending_if_absent(
            idempotency_key=key,
            resource_scope=scope,
            request_hash="abc123",
            created_at=_now_iso(),
            expires_at=_future_iso(),
            pending_timeout_seconds=30,
        )
        assert duplicate is False
    finally:
        await repo._graph_db.close()


@pytest.mark.asyncio
async def test_get_record_returns_record_after_create() -> None:
    """get_record returns the created record after create_pending_if_absent."""
    repo = _make_repo()
    key = f"key-{uuid4()}"
    scope = "PUT /items"
    try:
        await repo.create_pending_if_absent(
            idempotency_key=key,
            resource_scope=scope,
            request_hash="hash-x",
            created_at=_now_iso(),
            expires_at=_future_iso(),
            pending_timeout_seconds=30,
        )
        record = await repo.get_record(idempotency_key=key, resource_scope=scope)
        assert record is not None
        assert record.idempotency_key == key
        assert record.status == "pending"
    finally:
        await repo._graph_db.close()


@pytest.mark.asyncio
async def test_upsert_pending_creates_and_overwrites() -> None:
    """upsert_pending writes a record regardless of prior state."""
    repo = _make_repo()
    key = f"key-{uuid4()}"
    scope = "DELETE /items"
    try:
        record = await repo.upsert_pending(
            idempotency_key=key,
            resource_scope=scope,
            request_hash="hash-v1",
            created_at=_now_iso(),
            expires_at=_future_iso(),
            pending_timeout_seconds=30,
        )
        assert record.status == "pending"
        assert record.request_hash == "hash-v1"

        record2 = await repo.upsert_pending(
            idempotency_key=key,
            resource_scope=scope,
            request_hash="hash-v2",
            created_at=_now_iso(),
            expires_at=_future_iso(),
            pending_timeout_seconds=30,
        )
        assert record2.request_hash == "hash-v2"
    finally:
        await repo._graph_db.close()


@pytest.mark.asyncio
async def test_mark_completed_sets_status() -> None:
    """mark_completed transitions a pending record to completed status."""
    repo = _make_repo()
    key = f"key-{uuid4()}"
    scope = "POST /complete"
    try:
        await repo.create_pending_if_absent(
            idempotency_key=key,
            resource_scope=scope,
            request_hash="rhash",
            created_at=_now_iso(),
            expires_at=_future_iso(),
            pending_timeout_seconds=30,
        )
        await repo.mark_completed(
            idempotency_key=key,
            resource_scope=scope,
            request_hash="rhash",
            status_code=200,
            response_body='{"ok": true}',
            response_hash="resp-hash",
            updated_at=_now_iso(),
        )
        record = await repo.get_record(idempotency_key=key, resource_scope=scope)
        assert record is not None
        assert record.status == "completed"
    finally:
        await repo._graph_db.close()


@pytest.mark.asyncio
async def test_mark_failed_terminal_sets_status() -> None:
    """mark_failed_terminal transitions a pending record to failed_terminal status."""
    repo = _make_repo()
    key = f"key-{uuid4()}"
    scope = "POST /fail"
    try:
        await repo.create_pending_if_absent(
            idempotency_key=key,
            resource_scope=scope,
            request_hash="rhash-f",
            created_at=_now_iso(),
            expires_at=_future_iso(),
            pending_timeout_seconds=30,
        )
        await repo.mark_failed_terminal(
            idempotency_key=key,
            resource_scope=scope,
            request_hash="rhash-f",
            status_code=500,
            response_body='{"error": "server error"}',
            response_hash="resp-fail-hash",
            updated_at=_now_iso(),
        )
        record = await repo.get_record(idempotency_key=key, resource_scope=scope)
        assert record is not None
        assert record.status == "failed_terminal"
    finally:
        await repo._graph_db.close()


@pytest.mark.asyncio
async def test_delete_expired_removes_expired_records() -> None:
    """delete_expired returns a positive count when expired records exist."""
    repo = _make_repo()
    key = f"key-expired-{uuid4()}"
    scope = "POST /expire"
    try:
        await repo.upsert_pending(
            idempotency_key=key,
            resource_scope=scope,
            request_hash="exp-hash",
            created_at=_past_iso(3600),
            expires_at=_past_iso(1),
            pending_timeout_seconds=1,
        )
        deleted = await repo.delete_expired(now_iso=_now_iso())
        assert deleted >= 1
    finally:
        await repo._graph_db.close()
