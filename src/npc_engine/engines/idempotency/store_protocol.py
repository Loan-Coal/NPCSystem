"""
Module: store_protocol
Layer: engines
Purpose: Sessionless storage protocol for idempotency persistence backends. The
         concrete adapter (Neo4jIdempotencyRepository in graph/repositories/) holds
         a GraphDB and opens its own sessions, so IdempotencyService needs no session
         knowledge (DEC-122 / SEV-24).
Does NOT: provide a concrete database implementation or open Neo4j sessions.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.idempotency.service.IdempotencyService;
         implemented structurally by
         npc_engine.graph.repositories.idempotency_repository.Neo4jIdempotencyRepository.
"""

from __future__ import annotations

from typing import Protocol

from npc_engine.graph.idempotency_models import IdempotencyRecord


class IdempotencyStoreProtocol(Protocol):
    """Sessionless protocol for loading and mutating idempotency records."""

    async def ensure_constraints(self) -> None:
        """Create any required database constraints for idempotency records."""
        ...

    async def get_record(
        self,
        *,
        idempotency_key: str,
        resource_scope: str,
    ) -> IdempotencyRecord | None:
        """Fetch an idempotency record by key and scope.

        Args:
            idempotency_key: Client-supplied idempotency key.
            resource_scope: Method+path scope string.

        Returns:
            Matching IdempotencyRecord, or None if absent.
        """
        ...

    async def create_pending_if_absent(
        self,
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
            idempotency_key: Client-supplied idempotency key.
            resource_scope: Method+path scope string.
            request_hash: SHA-256 hex digest of the original request.
            status_code: HTTP status code of the failed response.
            response_body: Serialised response body string.
            response_hash: SHA-256 hex digest of the response.
            updated_at: ISO-8601 update timestamp.
        """
        ...

    async def delete_expired(self, *, now_iso: str) -> int:
        """Delete all records whose expiry timestamp is before now_iso.

        Args:
            now_iso: Current UTC time as ISO-8601 string used as the expiry cutoff.

        Returns:
            Number of records deleted.
        """
        ...
