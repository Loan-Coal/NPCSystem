"""
Module: tick_lease
Layer: scheduler
Purpose: Distributed lease/claim storage for scheduler ticks in Neo4j.
Does NOT: run engine handlers or advance clock state.
Dependencies injected: AsyncSession (caller-managed).
Used by: scheduler.tick_scheduler_engine
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from neo4j import AsyncSession

from npc_engine.graph.tick_lease_queries import (
    ensure_tick_lease_constraint,
    is_lease_done,
    mark_lease_done,
    mark_lease_failed,
    try_claim_lease,
)


class TickLeaseRepositoryProtocol(Protocol):
    """Protocol for distributed tick-lease coordination."""

    async def try_claim(self, session: AsyncSession, engine: str, tick_id: int) -> bool: ...

    async def mark_done(self, session: AsyncSession, engine: str, tick_id: int) -> bool: ...

    async def is_done(self, session: AsyncSession, engine: str, tick_id: int) -> bool: ...

    async def mark_failed(self, session: AsyncSession, engine: str, tick_id: int, error: str) -> None: ...


class TickLeaseRepository:
    """Stores per-engine tick claims in Neo4j for cross-worker coordination."""

    def __init__(self, scheduler_id: str, owner_id: str, lease_ttl_seconds: int) -> None:
        """Initialise the repository.

        Args:
            scheduler_id: Unique identifier for this scheduler instance.
            owner_id: Worker identifier used in lease ownership claims.
            lease_ttl_seconds: Lease duration; clamped to a minimum of 1.
        """
        self._scheduler_id = scheduler_id
        self._owner_id = owner_id
        self._lease_ttl_seconds = max(1, lease_ttl_seconds)

    async def ensure_constraints(self, session: AsyncSession) -> None:
        """Create the Neo4j uniqueness constraint for TickLease nodes if absent.

        Args:
            session: Active Neo4j async session.
        """
        await ensure_tick_lease_constraint(session)

    async def try_claim(self, session: AsyncSession, engine: str, tick_id: int) -> bool:
        """Attempt to claim the lease for this engine tick.

        Args:
            session: Active Neo4j async session.
            engine: Engine identifier (e.g. ``"gossip"`` or ``"event"``).
            tick_id: Tick to claim.

        Returns:
            True when the lease was successfully claimed; False if already owned
            by another worker or already completed.
        """
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        lease_until_ms = now_ms + self._lease_ttl_seconds * 1000
        return await try_claim_lease(
            session,
            scheduler_id=self._scheduler_id,
            owner_id=self._owner_id,
            engine=engine,
            tick_id=tick_id,
            now_ms=now_ms,
            lease_until_ms=lease_until_ms,
        )

    async def mark_done(self, session: AsyncSession, engine: str, tick_id: int) -> bool:
        """Mark the claimed lease as done.

        Args:
            session: Active Neo4j async session.
            engine: Engine identifier.
            tick_id: Tick to mark complete.

        Returns:
            True when the update matched an owned, claimed lease; False otherwise.
        """
        return await mark_lease_done(
            session,
            scheduler_id=self._scheduler_id,
            owner_id=self._owner_id,
            engine=engine,
            tick_id=tick_id,
        )

    async def is_done(self, session: AsyncSession, engine: str, tick_id: int) -> bool:
        """Return True when the lease record has status ``'done'``.

        Args:
            session: Active Neo4j async session.
            engine: Engine identifier.
            tick_id: Tick to query.

        Returns:
            True if the lease exists and its status is ``'done'``; False otherwise.
        """
        return await is_lease_done(
            session,
            scheduler_id=self._scheduler_id,
            engine=engine,
            tick_id=tick_id,
        )

    async def mark_failed(self, session: AsyncSession, engine: str, tick_id: int, error: str) -> None:
        """Record an error and expire the lease so another worker may retry.

        Args:
            session: Active Neo4j async session.
            engine: Engine identifier.
            tick_id: Tick that failed.
            error: Error string stored on the lease node (truncated to 500 chars).
        """
        await mark_lease_failed(
            session,
            scheduler_id=self._scheduler_id,
            owner_id=self._owner_id,
            engine=engine,
            tick_id=tick_id,
            error=error[:500],
        )
