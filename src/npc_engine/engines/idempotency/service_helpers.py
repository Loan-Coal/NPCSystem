"""
Module: service_helpers
Layer: engines
Purpose: Private helpers for idempotency preflight evaluation. All store calls are
         sessionless — the concrete adapter manages its own Neo4j sessions
         (DEC-122 / SEV-24).
Does NOT: manage sessions, expose public service API, or open database connections.
Dependencies injected: IdempotencyStoreProtocol, Settings.
Used by: npc_engine.engines.idempotency.service.IdempotencyService.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from npc_engine.config import Settings
from npc_engine.engines.idempotency.models import IdempotencyPreflightResult
from npc_engine.engines.idempotency.store_protocol import IdempotencyStoreProtocol
from npc_engine.graph.idempotency_models import IdempotencyRecord


async def create_pending(
    *,
    store: IdempotencyStoreProtocol,
    idempotency_key: str,
    resource_scope: str,
    request_hash: str,
    now: datetime,
    settings: Settings,
) -> None:
    """Upsert a pending record with an expiry derived from settings."""
    expires_at = now + timedelta(hours=settings.IDEMPOTENCY_RETENTION_HOURS)
    await store.upsert_pending(
        idempotency_key=idempotency_key,
        resource_scope=resource_scope,
        request_hash=request_hash,
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        pending_timeout_seconds=settings.IDEMPOTENCY_PENDING_TIMEOUT_SECONDS,
    )


async def create_pending_if_absent(
    *,
    store: IdempotencyStoreProtocol,
    idempotency_key: str,
    resource_scope: str,
    request_hash: str,
    now: datetime,
    settings: Settings,
) -> bool:
    """Create a pending record only if none exists; return True when created."""
    expires_at = now + timedelta(hours=settings.IDEMPOTENCY_RETENTION_HOURS)
    return await store.create_pending_if_absent(
        idempotency_key=idempotency_key,
        resource_scope=resource_scope,
        request_hash=request_hash,
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        pending_timeout_seconds=settings.IDEMPOTENCY_PENDING_TIMEOUT_SECONDS,
    )


async def evaluate_existing_record(
    *,
    store: IdempotencyStoreProtocol,
    record: IdempotencyRecord,
    idempotency_key: str,
    resource_scope: str,
    request_hash: str,
    now: datetime,
    settings: Settings,
) -> IdempotencyPreflightResult:
    """Evaluate an existing record and return the appropriate preflight decision."""
    if record.request_hash != request_hash:
        return IdempotencyPreflightResult(decision="conflict", request_hash=request_hash)

    if record.status in {"completed", "failed_terminal"}:
        return IdempotencyPreflightResult(
            decision="replay",
            request_hash=request_hash,
            response_status_code=record.response_status_code,
            response_body=record.response_body,
        )

    if is_pending_in_flight(
        record_created_at=record.created_at,
        timeout_seconds=record.pending_timeout_seconds,
        now=now,
    ):
        return IdempotencyPreflightResult(
            decision="in_flight",
            request_hash=request_hash,
        )

    await create_pending(
        store=store,
        idempotency_key=idempotency_key,
        resource_scope=resource_scope,
        request_hash=request_hash,
        now=now,
        settings=settings,
    )
    return IdempotencyPreflightResult(decision="proceed", request_hash=request_hash)


def is_pending_in_flight(*, record_created_at: str, timeout_seconds: int, now: datetime) -> bool:
    """Return True if the pending record is still within its in-flight window."""
    created_at = parse_datetime(record_created_at)
    cutoff = created_at + timedelta(seconds=timeout_seconds)
    return now <= cutoff


def parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 string and return a UTC-aware datetime."""
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resource_scope(*, method: str, path: str) -> str:
    """Return the METHOD:path scope string for an idempotency key."""
    return f"{method.upper()}:{path}"


def request_hash(*, method: str, path: str, query_string: str, body_bytes: bytes) -> str:
    """Return the SHA-256 hex digest of the request parameters."""
    payload = b"|".join(
        [
            method.upper().encode("utf-8"),
            path.encode("utf-8"),
            query_string.encode("utf-8"),
            body_bytes,
        ]
    )
    return hashlib.sha256(payload).hexdigest()


def response_hash(*, status_code: int, response_body: str) -> str:
    """Return the SHA-256 hex digest of the response."""
    payload = f"{status_code}|{response_body}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
