"""
store_protocol.py - Storage protocol for idempotency persistence backends.

Does NOT: provide concrete database implementation.

Dependencies injected: None.
"""

from typing import Protocol

from neo4j import AsyncSession

from engines.idempotency.models import IdempotencyRecord


class IdempotencyStoreProtocol(Protocol):
    """Protocol for loading and mutating idempotency records."""

    async def ensure_constraints(self, session: AsyncSession) -> None: ...

    async def get_record(
        self,
        session: AsyncSession,
        *,
        idempotency_key: str,
        resource_scope: str,
    ) -> IdempotencyRecord | None: ...

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
    ) -> bool: ...

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
    ) -> IdempotencyRecord: ...

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
    ) -> None: ...

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
    ) -> None: ...

    async def delete_expired(self, session: AsyncSession, *, now_iso: str) -> int: ...
