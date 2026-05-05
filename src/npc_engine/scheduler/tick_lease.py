"""
tick_lease.py - Distributed lease/claim storage for scheduler ticks in Neo4j.

Does NOT: run engine handlers or advance clock state.

Dependencies injected: AsyncSession.
"""

from datetime import datetime, timezone
from typing import Protocol

from neo4j import AsyncSession


CYPHER_ENSURE_TICK_LEASE_CONSTRAINT = """
CREATE CONSTRAINT tick_lease_key IF NOT EXISTS
FOR (l:TickLease)
REQUIRE (l.scheduler_id, l.engine, l.tick_id) IS UNIQUE
"""


CYPHER_TRY_CLAIM = """
MERGE (l:TickLease {scheduler_id: $scheduler_id, engine: $engine, tick_id: $tick_id})
ON CREATE SET
    l.owner = $owner_id,
    l.lease_until_ms = $lease_until_ms,
    l.status = 'claimed',
    l.updated_at = datetime()
WITH l
CALL {
    WITH l
    WHERE l.status = 'done'
    RETURN false AS claimed
    UNION
    WITH l
    WHERE l.status <> 'done' AND (l.owner = $owner_id OR coalesce(l.lease_until_ms, 0) <= $now_ms)
    SET l.owner = $owner_id,
        l.lease_until_ms = $lease_until_ms,
        l.status = 'claimed',
        l.updated_at = datetime()
    RETURN true AS claimed
    UNION
    WITH l
    WHERE l.status <> 'done' AND NOT (l.owner = $owner_id OR coalesce(l.lease_until_ms, 0) <= $now_ms)
    RETURN false AS claimed
}
RETURN claimed
"""


CYPHER_MARK_DONE = """
MATCH (l:TickLease {scheduler_id: $scheduler_id, engine: $engine, tick_id: $tick_id})
WHERE l.owner = $owner_id AND l.status = 'claimed'
SET l.status = 'done',
    l.lease_until_ms = 0,
    l.completed_at = datetime(),
    l.updated_at = datetime()
RETURN true AS done
"""


CYPHER_MARK_FAILED = """
MATCH (l:TickLease {scheduler_id: $scheduler_id, engine: $engine, tick_id: $tick_id})
WHERE l.owner = $owner_id AND l.status = 'claimed'
SET l.lease_until_ms = 0,
    l.last_error = $error,
    l.updated_at = datetime()
RETURN true AS failed
"""


CYPHER_IS_DONE = """
MATCH (l:TickLease {scheduler_id: $scheduler_id, engine: $engine, tick_id: $tick_id})
RETURN coalesce(l.status, '') = 'done' AS done
"""


class TickLeaseRepositoryProtocol(Protocol):
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

        await session.run(CYPHER_ENSURE_TICK_LEASE_CONSTRAINT)

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
        result = await session.run(
            CYPHER_TRY_CLAIM,
            scheduler_id=self._scheduler_id,
            owner_id=self._owner_id,
            engine=engine,
            tick_id=tick_id,
            now_ms=now_ms,
            lease_until_ms=lease_until_ms,
        )
        row = await result.single()
        return bool(row["claimed"]) if row is not None else False

    async def mark_done(self, session: AsyncSession, engine: str, tick_id: int) -> bool:
        """Mark the claimed lease as done.

        Args:
            session: Active Neo4j async session.
            engine: Engine identifier.
            tick_id: Tick to mark complete.

        Returns:
            True when the update matched an owned, claimed lease; False otherwise.
        """

        result = await session.run(
            CYPHER_MARK_DONE,
            scheduler_id=self._scheduler_id,
            owner_id=self._owner_id,
            engine=engine,
            tick_id=tick_id,
        )
        row = await result.single()
        return bool(row["done"]) if row is not None else False

    async def is_done(self, session: AsyncSession, engine: str, tick_id: int) -> bool:
        """Return True when the lease record has status ``'done'``.

        Args:
            session: Active Neo4j async session.
            engine: Engine identifier.
            tick_id: Tick to query.

        Returns:
            True if the lease exists and its status is ``'done'``; False otherwise.
        """

        result = await session.run(
            CYPHER_IS_DONE,
            scheduler_id=self._scheduler_id,
            engine=engine,
            tick_id=tick_id,
        )
        row = await result.single()
        return bool(row["done"]) if row is not None else False

    async def mark_failed(self, session: AsyncSession, engine: str, tick_id: int, error: str) -> None:
        """Record an error and expire the lease so another worker may retry.

        Args:
            session: Active Neo4j async session.
            engine: Engine identifier.
            tick_id: Tick that failed.
            error: Error string stored on the lease node (truncated to 500 chars).
        """

        await session.run(
            CYPHER_MARK_FAILED,
            scheduler_id=self._scheduler_id,
            owner_id=self._owner_id,
            engine=engine,
            tick_id=tick_id,
            error=error[:500],
        )
