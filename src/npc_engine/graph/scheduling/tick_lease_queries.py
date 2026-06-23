"""
Module: tick_lease_queries
Layer: graph
Purpose: Cypher queries for TickLease distributed tick-claim coordination in Neo4j.
Does NOT: manage lease TTL math or own lease business logic.
Dependencies injected: AsyncSession (caller-managed).
Used by: scheduler.tick_lease
"""
from __future__ import annotations

from neo4j import AsyncSession

_CYPHER_ENSURE_CONSTRAINT = """
CREATE CONSTRAINT tick_lease_key IF NOT EXISTS
FOR (l:TickLease)
REQUIRE (l.scheduler_id, l.engine, l.tick_id) IS UNIQUE
"""

_CYPHER_TRY_CLAIM = """
MERGE (l:TickLease {scheduler_id: $scheduler_id, engine: $engine, tick_id: $tick_id})
ON CREATE SET
    l.owner = $owner_id,
    l.lease_until_ms = $lease_until_ms,
    l.status = 'claimed',
    l.updated_at = datetime()
WITH l,
     CASE
       WHEN l.status = 'done' THEN false
       WHEN l.owner = $owner_id OR coalesce(l.lease_until_ms, 0) <= $now_ms THEN true
       ELSE false
     END AS should_claim
FOREACH (x IN CASE WHEN should_claim THEN [1] ELSE [] END |
    SET l.owner = $owner_id,
        l.lease_until_ms = $lease_until_ms,
        l.status = 'claimed',
        l.updated_at = datetime()
)
RETURN should_claim AS claimed
"""

_CYPHER_MARK_DONE = """
MATCH (l:TickLease {scheduler_id: $scheduler_id, engine: $engine, tick_id: $tick_id})
WHERE l.owner = $owner_id AND l.status = 'claimed'
SET l.status = 'done',
    l.lease_until_ms = 0,
    l.completed_at = datetime(),
    l.updated_at = datetime()
RETURN true AS done
"""

_CYPHER_MARK_FAILED = """
MATCH (l:TickLease {scheduler_id: $scheduler_id, engine: $engine, tick_id: $tick_id})
WHERE l.owner = $owner_id AND l.status = 'claimed'
SET l.lease_until_ms = 0,
    l.last_error = $error,
    l.updated_at = datetime()
RETURN true AS failed
"""

_CYPHER_IS_DONE = """
MATCH (l:TickLease {scheduler_id: $scheduler_id, engine: $engine, tick_id: $tick_id})
RETURN coalesce(l.status, '') = 'done' AS done
"""


async def ensure_tick_lease_constraint(session: AsyncSession) -> None:
    """Create the TickLease uniqueness constraint if it does not already exist.

    Args:
        session: Active Neo4j async session.
    """
    await session.run(_CYPHER_ENSURE_CONSTRAINT)


async def try_claim_lease(
    session: AsyncSession,
    scheduler_id: str,
    owner_id: str,
    engine: str,
    tick_id: int,
    now_ms: int,
    lease_until_ms: int,
) -> bool:
    """Attempt to claim or reclaim a TickLease node.

    Args:
        session: Active Neo4j async session.
        scheduler_id: Scheduler instance identifier.
        owner_id: Worker claiming the lease.
        engine: Engine key (e.g. 'gossip').
        tick_id: Tick to claim.
        now_ms: Current epoch-milliseconds for expiry comparison.
        lease_until_ms: Epoch-milliseconds when the lease expires.

    Returns:
        True if the lease was successfully claimed; False if already owned or done.
    """
    result = await session.run(
        _CYPHER_TRY_CLAIM,
        scheduler_id=scheduler_id,
        owner_id=owner_id,
        engine=engine,
        tick_id=tick_id,
        now_ms=now_ms,
        lease_until_ms=lease_until_ms,
    )
    row = await result.single()
    return bool(row["claimed"]) if row is not None else False


async def mark_lease_done(
    session: AsyncSession,
    scheduler_id: str,
    owner_id: str,
    engine: str,
    tick_id: int,
) -> bool:
    """Mark a claimed lease as done.

    Args:
        session: Active Neo4j async session.
        scheduler_id: Scheduler instance identifier.
        owner_id: Worker that owns the lease.
        engine: Engine key.
        tick_id: Tick to mark complete.

    Returns:
        True if the lease was updated; False if not found or not claimable.
    """
    result = await session.run(
        _CYPHER_MARK_DONE,
        scheduler_id=scheduler_id,
        owner_id=owner_id,
        engine=engine,
        tick_id=tick_id,
    )
    row = await result.single()
    return bool(row["done"]) if row is not None else False


async def mark_lease_failed(
    session: AsyncSession,
    scheduler_id: str,
    owner_id: str,
    engine: str,
    tick_id: int,
    error: str,
) -> None:
    """Expire a lease and record the error string.

    Args:
        session: Active Neo4j async session.
        scheduler_id: Scheduler instance identifier.
        owner_id: Worker that holds the lease.
        engine: Engine key.
        tick_id: Tick that failed.
        error: Error message (will be stored on the TickLease node).
    """
    await session.run(
        _CYPHER_MARK_FAILED,
        scheduler_id=scheduler_id,
        owner_id=owner_id,
        engine=engine,
        tick_id=tick_id,
        error=error,
    )


async def is_lease_done(
    session: AsyncSession,
    scheduler_id: str,
    engine: str,
    tick_id: int,
) -> bool:
    """Return True when the TickLease node has status 'done'.

    Args:
        session: Active Neo4j async session.
        scheduler_id: Scheduler instance identifier.
        engine: Engine key.
        tick_id: Tick to query.

    Returns:
        True if the lease exists and its status is 'done'; False otherwise.
    """
    result = await session.run(
        _CYPHER_IS_DONE,
        scheduler_id=scheduler_id,
        engine=engine,
        tick_id=tick_id,
    )
    row = await result.single()
    return bool(row["done"]) if row is not None else False
