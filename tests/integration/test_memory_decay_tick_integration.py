"""
test_memory_decay_tick_integration.py - Integration test for F1.7: the forgetting-decay
tick reduces a low-salience memory's vividness over ticks against a live Neo4j.

Does NOT: validate HTTP routes or LLM calls.

Dependencies injected: Neo4j test environment via env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.engines.memory.memory_engine import MemoryEngine
from npc_engine.engines.memory.memory_decay_tick import MemoryDecayTick


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


async def _create_memory(tx, mem_id: str, vividness: int) -> None:
    await tx.run(
        "CREATE (m:Memory {id: $id, vividness: $vividness, emotional_charge: 0})",
        id=mem_id, vividness=vividness,
    )


async def _read_vividness(tx, mem_id: str) -> int:
    result = await tx.run("MATCH (m:Memory {id: $id}) RETURN m.vividness AS v", id=mem_id)
    record = await result.single()
    return int(record["v"])


async def _cleanup(tx, mem_id: str) -> None:
    await tx.run("MATCH (m:Memory {id: $id}) DETACH DELETE m", id=mem_id)


@pytest.mark.asyncio
async def test_low_salience_memory_decays_over_ticks() -> None:
    """A low-charge memory's vividness strictly decreases across two on-interval decay ticks."""
    uri, user, password = _skip_if_no_neo4j()

    mem_id = _uid("mem")
    start_vividness = 80

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_memory(tx, mem_id, start_vividness)
                await tx.commit()

            adapter = MemoryDecayTick(memory_engine=MemoryEngine(), interval=1)
            await adapter.run_tick(session=session, tick_id=1)
            async with await session.begin_transaction() as tx:
                after_one = await _read_vividness(tx, mem_id)
            await adapter.run_tick(session=session, tick_id=2)
            async with await session.begin_transaction() as tx:
                after_two = await _read_vividness(tx, mem_id)

        assert after_one < start_vividness
        assert after_two < after_one
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, mem_id)
                await tx.commit()
        await driver.close()
