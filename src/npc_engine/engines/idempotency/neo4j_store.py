"""
neo4j_store.py - Neo4j persistence backend for idempotency records.

Does NOT: decide replay/conflict semantics.

Dependencies injected: AsyncSession.
"""

from typing import Any

from neo4j import AsyncSession

from npc_engine.engines.idempotency.models import IdempotencyRecord
from npc_engine.engines.idempotency.neo4j_queries import (
    CYPHER_CREATE_PENDING_IF_ABSENT,
    CYPHER_DELETE_EXPIRED,
    CYPHER_ENSURE_IDEMPOTENCY_CONSTRAINT,
    CYPHER_GET_RECORD,
    CYPHER_MARK_COMPLETE,
    CYPHER_UPSERT_PENDING,
)


class Neo4jIdempotencyStore:
    """Persists idempotency records inside Neo4j."""

    async def ensure_constraints(self, session: AsyncSession) -> None:
        """Create the uniqueness constraint on idempotency records if absent.

        Args:
            session: Active Neo4j async session.
        """
        await session.run(CYPHER_ENSURE_IDEMPOTENCY_CONSTRAINT)

    async def get_record(
        self,
        session: AsyncSession,
        *,
        idempotency_key: str,
        resource_scope: str,
    ) -> IdempotencyRecord | None:
        """Fetch an idempotency record by key and scope.

        Args:
            session: Active Neo4j async session.
            idempotency_key: Client-supplied idempotency key.
            resource_scope: Method+path scope string.

        Returns:
            Matching IdempotencyRecord, or None if absent.
        """
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
        """Upsert a pending record, overwriting any prior state.

        Args:
            session: Active Neo4j async session.
            idempotency_key: Client-supplied idempotency key.
            resource_scope: Method+path scope string.
            request_hash: SHA-256 hex digest of the request.
            created_at: ISO-8601 creation timestamp.
            expires_at: ISO-8601 expiry timestamp.
            pending_timeout_seconds: Seconds before a pending record is considered stale.

        Returns:
            The upserted IdempotencyRecord.

        Raises:
            RuntimeError: If the Cypher query returns no row.
        """
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
        """Create a pending record only if none exists for the key+scope pair.

        Args:
            session: Active Neo4j async session.
            idempotency_key: Client-supplied idempotency key.
            resource_scope: Method+path scope string.
            request_hash: SHA-256 hex digest of the request.
            created_at: ISO-8601 creation timestamp.
            expires_at: ISO-8601 expiry timestamp.
            pending_timeout_seconds: Seconds before a pending record is considered stale.

        Returns:
            True if a new record was created, False if one already existed.
        """
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
        """Mark an idempotency record as completed with a stored response.

        Args:
            session: Active Neo4j async session.
            idempotency_key: Client-supplied idempotency key.
            resource_scope: Method+path scope string.
            request_hash: SHA-256 hex digest of the original request.
            status_code: HTTP status code of the completed response.
            response_body: Serialised response body string.
            response_hash: SHA-256 hex digest of the response.
            updated_at: ISO-8601 update timestamp.

        Raises:
            RuntimeError: If no matching record is found to update.
        """
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
        """Mark an idempotency record as permanently failed.

        Args:
            session: Active Neo4j async session.
            idempotency_key: Client-supplied idempotency key.
            resource_scope: Method+path scope string.
            request_hash: SHA-256 hex digest of the original request.
            status_code: HTTP status code of the failed response.
            response_body: Serialised response body string.
            response_hash: SHA-256 hex digest of the response.
            updated_at: ISO-8601 update timestamp.

        Raises:
            RuntimeError: If no matching record is found to update.
        """
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
        """Delete all records whose expires_at is before now_iso.

        Args:
            session: Active Neo4j async session.
            now_iso: Current UTC time as ISO-8601 string used as the expiry cutoff.

        Returns:
            Number of records deleted.
        """
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
