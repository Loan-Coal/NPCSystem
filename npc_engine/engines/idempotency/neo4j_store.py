"""
neo4j_store.py - Neo4j persistence backend for idempotency records.

Does NOT: decide replay/conflict semantics.

Dependencies injected: AsyncSession.
"""

from typing import Any

from neo4j import AsyncSession

from engines.idempotency.models import IdempotencyRecord


CYPHER_ENSURE_IDEMPOTENCY_CONSTRAINT = """
CREATE CONSTRAINT idempotency_record_key IF NOT EXISTS
FOR (r:IdempotencyRecord)
REQUIRE (r.idempotency_key, r.resource_scope) IS UNIQUE
"""

CYPHER_GET_RECORD = """
MATCH (r:IdempotencyRecord {idempotency_key: $idempotency_key, resource_scope: $resource_scope})
RETURN r
LIMIT 1
"""

CYPHER_UPSERT_PENDING = """
MERGE (r:IdempotencyRecord {idempotency_key: $idempotency_key, resource_scope: $resource_scope})
SET r.request_hash = $request_hash,
    r.status = 'pending',
    r.response_status_code = null,
    r.response_body = null,
    r.response_hash = null,
    r.created_at = datetime($created_at),
    r.expires_at = datetime($expires_at),
    r.pending_timeout_seconds = $pending_timeout_seconds,
    r.updated_at = datetime($created_at)
RETURN r
"""

CYPHER_CREATE_PENDING_IF_ABSENT = """
MERGE (r:IdempotencyRecord {idempotency_key: $idempotency_key, resource_scope: $resource_scope})
ON CREATE SET r.request_hash = $request_hash,
              r.status = 'pending',
              r.response_status_code = null,
              r.response_body = null,
              r.response_hash = null,
              r.created_at = datetime($created_at),
              r.expires_at = datetime($expires_at),
              r.pending_timeout_seconds = $pending_timeout_seconds,
              r.updated_at = datetime($created_at),
              r._just_created = true
WITH r, coalesce(r._just_created, false) AS created
REMOVE r._just_created
RETURN created
"""

CYPHER_MARK_COMPLETE = """
MATCH (r:IdempotencyRecord {idempotency_key: $idempotency_key, resource_scope: $resource_scope})
WHERE r.request_hash = $request_hash
SET r.status = $status,
    r.response_status_code = $status_code,
    r.response_body = $response_body,
    r.response_hash = $response_hash,
    r.updated_at = datetime($updated_at)
RETURN count(r) AS updated_count
"""

CYPHER_DELETE_EXPIRED = """
MATCH (r:IdempotencyRecord)
WHERE r.expires_at < datetime($now_iso)
WITH collect(r) AS records, count(r) AS deleted_count
FOREACH (record IN records | DETACH DELETE record)
RETURN deleted_count
"""


class Neo4jIdempotencyStore:
    """Persists idempotency records inside Neo4j."""

    async def ensure_constraints(self, session: AsyncSession) -> None:
        await session.run(CYPHER_ENSURE_IDEMPOTENCY_CONSTRAINT)

    async def get_record(
        self,
        session: AsyncSession,
        *,
        idempotency_key: str,
        resource_scope: str,
    ) -> IdempotencyRecord | None:
        result = await session.run(
            CYPHER_GET_RECORD,
            idempotency_key=idempotency_key,
            resource_scope=resource_scope,
        )
        row = await result.single()
        if row is None:
            return None
        return _map_record(properties=row["r"])

    async def upsert_pending(
        self,
        session: AsyncSession,
        *,
        idempotency_key: str,
        resource_scope: str,
        request_hash: str,
        created_at: str,
        expires_at: str,
        pending_timeout_seconds: int,
    ) -> IdempotencyRecord:
        result = await session.run(
            CYPHER_UPSERT_PENDING,
            idempotency_key=idempotency_key,
            resource_scope=resource_scope,
            request_hash=request_hash,
            created_at=created_at,
            expires_at=expires_at,
            pending_timeout_seconds=pending_timeout_seconds,
        )
        row = await result.single()
        if row is None:
            raise RuntimeError("Unable to upsert idempotency record")
        return _map_record(properties=row["r"])

    async def create_pending_if_absent(
        self,
        session: AsyncSession,
        *,
        idempotency_key: str,
        resource_scope: str,
        request_hash: str,
        created_at: str,
        expires_at: str,
        pending_timeout_seconds: int,
    ) -> bool:
        result = await session.run(
            CYPHER_CREATE_PENDING_IF_ABSENT,
            idempotency_key=idempotency_key,
            resource_scope=resource_scope,
            request_hash=request_hash,
            created_at=created_at,
            expires_at=expires_at,
            pending_timeout_seconds=pending_timeout_seconds,
        )
        row = await result.single()
        if row is None:
            return False
        return bool(row["created"])

    async def mark_completed(
        self,
        session: AsyncSession,
        *,
        idempotency_key: str,
        resource_scope: str,
        request_hash: str,
        status_code: int,
        response_body: str,
        response_hash: str,
        updated_at: str,
    ) -> None:
        await _mark_terminal(
            session=session,
            status="completed",
            idempotency_key=idempotency_key,
            resource_scope=resource_scope,
            request_hash=request_hash,
            status_code=status_code,
            response_body=response_body,
            response_hash=response_hash,
            updated_at=updated_at,
        )

    async def mark_failed_terminal(
        self,
        session: AsyncSession,
        *,
        idempotency_key: str,
        resource_scope: str,
        request_hash: str,
        status_code: int,
        response_body: str,
        response_hash: str,
        updated_at: str,
    ) -> None:
        await _mark_terminal(
            session=session,
            status="failed_terminal",
            idempotency_key=idempotency_key,
            resource_scope=resource_scope,
            request_hash=request_hash,
            status_code=status_code,
            response_body=response_body,
            response_hash=response_hash,
            updated_at=updated_at,
        )

    async def delete_expired(self, session: AsyncSession, *, now_iso: str) -> int:
        result = await session.run(CYPHER_DELETE_EXPIRED, now_iso=now_iso)
        row = await result.single()
        return int(row["deleted_count"]) if row is not None else 0


async def _mark_terminal(
    session: AsyncSession,
    *,
    status: str,
    idempotency_key: str,
    resource_scope: str,
    request_hash: str,
    status_code: int,
    response_body: str,
    response_hash: str,
    updated_at: str,
) -> None:
    result = await session.run(
        CYPHER_MARK_COMPLETE,
        idempotency_key=idempotency_key,
        resource_scope=resource_scope,
        request_hash=request_hash,
        status=status,
        status_code=status_code,
        response_body=response_body,
        response_hash=response_hash,
        updated_at=updated_at,
    )
    row = await result.single()
    updated_count = int(row["updated_count"]) if row is not None else 0
    if updated_count != 1:
        raise RuntimeError("Unable to mark idempotency record terminal state")


def _map_record(properties: Any) -> IdempotencyRecord:
    payload = dict(properties)
    payload["created_at"] = _serialize_datetime(payload.get("created_at"))
    payload["expires_at"] = _serialize_datetime(payload.get("expires_at"))
    payload["updated_at"] = _serialize_datetime(payload.get("updated_at"))
    return IdempotencyRecord.model_validate(payload)


def _serialize_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)
