"""
store_protocol.py - Storage protocol for idempotency persistence backends.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: provide concrete database implementation.

Dependencies injected: None.
"""
from __future__ import annotations

from typing import Protocol

from neo4j import AsyncSession

from npc_engine.graph.idempotency_models import IdempotencyRecord


class IdempotencyStoreProtocol(Protocol):
    """Protocol for loading and mutating idempotency records."""

    async def ensure_constraints(self, session: AsyncSession) -> None:
        """Create any required database constraints for idempotency records.

        Args:
            session: Active Neo4j async session.
        """
        ...

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
        ...

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
        ...

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
        """
        ...

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
        """Mark a record as successfully completed with a stored response.

        Args:
            session: Active Neo4j async session.
            idempotency_key: Client-supplied idempotency key.
            resource_scope: Method+path scope string.
            request_hash: SHA-256 hex digest of the original request.
            status_code: HTTP status code of the completed response.
            response_body: Serialised response body string.
            response_hash: SHA-256 hex digest of the response.
            updated_at: ISO-8601 update timestamp.
        """
        ...

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
        """Mark a record as permanently failed.

        Args:
            session: Active Neo4j async session.
            idempotency_key: Client-supplied idempotency key.
            resource_scope: Method+path scope string.
            request_hash: SHA-256 hex digest of the original request.
            status_code: HTTP status code of the failed response.
            response_body: Serialised response body string.
            response_hash: SHA-256 hex digest of the response.
            updated_at: ISO-8601 update timestamp.
        """
        ...

    async def delete_expired(self, session: AsyncSession, *, now_iso: str) -> int:
        """Delete all records whose expiry timestamp is before now_iso.

        Args:
            session: Active Neo4j async session.
            now_iso: Current UTC time as ISO-8601 string used as the expiry cutoff.

        Returns:
            Number of records deleted.
        """
        ...
