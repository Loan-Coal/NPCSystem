"""
Module: idempotency_repository
Layer: graph
Purpose: Neo4j adapter for the idempotency domain. Holds a GraphDB, opens a session
         per operation, and delegates to Neo4jIdempotencyStore, so IdempotencyService
         depends on IdempotencyStoreProtocol and holds no Neo4j session (DEC-122 / SEV-24).
Does NOT: decide replay/conflict semantics or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api/dependencies_stores.get_idempotency_service.
"""

from __future__ import annotations

from npc_engine.graph.db import GraphDB
from npc_engine.graph.idempotency_models import IdempotencyRecord
from npc_engine.graph.idempotency_writer import Neo4jIdempotencyStore


class Neo4jIdempotencyRepository:
    """Session-per-call Neo4j adapter for idempotency records (IdempotencyStoreProtocol)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db
        self._store = Neo4jIdempotencyStore()

    async def ensure_constraints(self) -> None:
        """Create the uniqueness constraint on idempotency records if absent."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await self._store.ensure_constraints(session=session)

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
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await self._store.get_record(
                session=session,
                idempotency_key=idempotency_key,
                resource_scope=resource_scope,
            )

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
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await self._store.create_pending_if_absent(
                session=session,
                idempotency_key=idempotency_key,
                resource_scope=resource_scope,
                request_hash=request_hash,
                created_at=created_at,
                expires_at=expires_at,
                pending_timeout_seconds=pending_timeout_seconds,
            )

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
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await self._store.upsert_pending(
                session=session,
                idempotency_key=idempotency_key,
                resource_scope=resource_scope,
                request_hash=request_hash,
                created_at=created_at,
                expires_at=expires_at,
                pending_timeout_seconds=pending_timeout_seconds,
            )

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
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await self._store.mark_completed(
                session=session,
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
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await self._store.mark_failed_terminal(
                session=session,
                idempotency_key=idempotency_key,
                resource_scope=resource_scope,
                request_hash=request_hash,
                status_code=status_code,
                response_body=response_body,
                response_hash=response_hash,
                updated_at=updated_at,
            )

    async def delete_expired(self, *, now_iso: str) -> int:
        """Delete all records whose expires_at is before now_iso.

        Args:
            now_iso: Current UTC time as ISO-8601 string used as the expiry cutoff.

        Returns:
            Number of records deleted.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await self._store.delete_expired(session=session, now_iso=now_iso)
