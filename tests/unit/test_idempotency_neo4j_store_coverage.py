"""
test_idempotency_neo4j_store_coverage.py - Unit tests for idempotency Neo4j store.

Does NOT: connect to a real Neo4j instance.

Dependencies injected: mock AsyncSession.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.idempotency_writer import Neo4jIdempotencyStore


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _record_props(
    key: str = "key-1",
    scope: str = "POST /v1/interact",
    status: str = "pending",
    expires_in_seconds: int = 3600,
) -> dict:
    now = _now()
    return {
        "idempotency_key": key,
        "resource_scope": scope,
        "request_hash": "abc123",
        "status": status,
        "response_status_code": None,
        "response_body": None,
        "response_hash": None,
        "created_at": _iso(now),
        "expires_at": _iso(now + timedelta(seconds=expires_in_seconds)),
        "pending_timeout_seconds": 30,
        "updated_at": None,
    }


def _make_session_with_record(props: dict | None) -> AsyncMock:
    """Return mock session whose single() returns a row with 'r' = props, or None."""
    cursor = AsyncMock()
    if props is None:
        cursor.single = AsyncMock(return_value=None)
    else:
        row = MagicMock()
        row.__getitem__ = lambda self, key: props if key == "r" else None
        cursor.single = AsyncMock(return_value=row)
    cursor.consume = AsyncMock()
    session = AsyncMock()
    session.run = AsyncMock(return_value=cursor)
    return session


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_record_returns_record_when_present() -> None:
    """get_record must return a populated IdempotencyRecord when a matching row exists."""
    props = _record_props()
    session = _make_session_with_record(props)
    store = Neo4jIdempotencyStore()

    record = await store.get_record(
        session, idempotency_key="key-1", resource_scope="POST /v1/interact"
    )

    assert record is not None
    assert record.idempotency_key == "key-1"
    assert record.status == "pending"


@pytest.mark.asyncio
async def test_get_record_returns_none_when_absent() -> None:
    """get_record must return None when no matching record is found."""
    session = _make_session_with_record(None)
    store = Neo4jIdempotencyStore()

    record = await store.get_record(
        session, idempotency_key="missing-key", resource_scope="POST /v1/interact"
    )

    assert record is None


# ---------------------------------------------------------------------------
# upsert_pending
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_pending_returns_record() -> None:
    """upsert_pending must return an IdempotencyRecord on success."""
    props = _record_props()
    session = _make_session_with_record(props)
    store = Neo4jIdempotencyStore()
    now = _now()

    record = await store.upsert_pending(
        session,
        idempotency_key="key-1",
        resource_scope="POST /v1/interact",
        request_hash="abc123",
        created_at=_iso(now),
        expires_at=_iso(now + timedelta(hours=1)),
        pending_timeout_seconds=30,
    )

    assert record.idempotency_key == "key-1"
    assert record.status == "pending"


@pytest.mark.asyncio
async def test_upsert_pending_raises_when_no_row_returned() -> None:
    """upsert_pending must raise RuntimeError when Cypher returns no row."""
    session = _make_session_with_record(None)
    store = Neo4jIdempotencyStore()
    now = _now()

    with pytest.raises(RuntimeError, match="Unable to upsert"):
        await store.upsert_pending(
            session,
            idempotency_key="key-1",
            resource_scope="POST /v1/interact",
            request_hash="abc123",
            created_at=_iso(now),
            expires_at=_iso(now + timedelta(hours=1)),
            pending_timeout_seconds=30,
        )


# ---------------------------------------------------------------------------
# create_pending_if_absent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_pending_if_absent_true_when_created() -> None:
    """create_pending_if_absent must return True when a new record is created."""
    cursor = AsyncMock()
    row = MagicMock()
    row.__getitem__ = lambda self, key: True if key == "created" else None
    cursor.single = AsyncMock(return_value=row)
    cursor.consume = AsyncMock()
    session = AsyncMock()
    session.run = AsyncMock(return_value=cursor)

    store = Neo4jIdempotencyStore()
    now = _now()

    created = await store.create_pending_if_absent(
        session,
        idempotency_key="key-new",
        resource_scope="POST /v1/interact",
        request_hash="abc123",
        created_at=_iso(now),
        expires_at=_iso(now + timedelta(hours=1)),
        pending_timeout_seconds=30,
    )

    assert created is True


@pytest.mark.asyncio
async def test_create_pending_if_absent_false_when_already_exists() -> None:
    """create_pending_if_absent must return False when record already exists (created=False)."""
    cursor = AsyncMock()
    row = MagicMock()
    row.__getitem__ = lambda self, key: False if key == "created" else None
    cursor.single = AsyncMock(return_value=row)
    cursor.consume = AsyncMock()
    session = AsyncMock()
    session.run = AsyncMock(return_value=cursor)

    store = Neo4jIdempotencyStore()
    now = _now()

    created = await store.create_pending_if_absent(
        session,
        idempotency_key="key-existing",
        resource_scope="POST /v1/interact",
        request_hash="abc123",
        created_at=_iso(now),
        expires_at=_iso(now + timedelta(hours=1)),
        pending_timeout_seconds=30,
    )

    assert created is False


# ---------------------------------------------------------------------------
# delete_expired
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_expired_returns_count() -> None:
    """delete_expired must return the number of deleted records."""
    cursor = AsyncMock()
    row = MagicMock()
    row.__getitem__ = lambda self, key: 3 if key == "deleted_count" else None
    cursor.single = AsyncMock(return_value=row)
    cursor.consume = AsyncMock()
    session = AsyncMock()
    session.run = AsyncMock(return_value=cursor)

    store = Neo4jIdempotencyStore()
    count = await store.delete_expired(session, now_iso=_iso(_now()))

    assert count == 3


@pytest.mark.asyncio
async def test_delete_expired_returns_zero_on_no_row() -> None:
    """delete_expired must return 0 when Cypher returns no row."""
    session = _make_session_with_record(None)
    store = Neo4jIdempotencyStore()

    count = await store.delete_expired(session, now_iso=_iso(_now()))

    assert count == 0
