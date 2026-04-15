"""
test_tick_lease_repository.py - Integration tests for Neo4j-backed tick lease claims.

Does NOT: test scheduler routing behavior.

Dependencies injected: Neo4j test environment via env vars.
"""

import asyncio
import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from scheduler.tick_lease import TickLeaseRepository


@pytest.mark.asyncio
async def test_tick_lease_claim_is_single_owner_under_contention() -> None:
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD are required")

    scheduler_id = f"test-{uuid4()}"
    worker_a = TickLeaseRepository(scheduler_id=scheduler_id, owner_id="worker-a", lease_ttl_seconds=30)
    worker_b = TickLeaseRepository(scheduler_id=scheduler_id, owner_id="worker-b", lease_ttl_seconds=30)

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            await worker_a.ensure_constraints(session=session)

        async def claim(repo: TickLeaseRepository) -> bool:
            async with driver.session() as session:
                return await repo.try_claim(session=session, engine="event", tick_id=42)

        claimed_a, claimed_b = await asyncio.gather(claim(worker_a), claim(worker_b))
        assert (claimed_a, claimed_b) in {(True, False), (False, True)}
    finally:
        await driver.close()
