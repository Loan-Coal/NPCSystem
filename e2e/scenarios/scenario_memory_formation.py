"""
scenario_memory_formation.py - E2E scenario for Feature 3.2: Memory nodes and formation.

Requires: live Neo4j instance, running API server on localhost:8000.
Run with: python e2e/scenarios/scenario_memory_formation.py

Steps:
  1. Seed a Character node.
  2. Create a Memory via MemoryEngine (high-arousal path).
  3. Assert the Memory node exists in the graph.
  4. Trigger day advance via the clock API.
  5. Assert vividness has decayed on the Memory node.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

from neo4j import AsyncGraphDatabase

_BOLT = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))

_CHAR_ID = f"e2e_mem_char_{uuid.uuid4().hex[:8]}"
_MEM_CONTENT = "The player threatened the innkeeper in front of the guard."


async def _seed_character(session) -> None:
    await session.run(
        "MERGE (c:Character {id: $id}) SET c.name = 'Test NPC', c.is_active = true",
        id=_CHAR_ID,
    )


async def _cleanup(session) -> None:
    await session.run(
        "MATCH (c:Character {id: $id})-[:REMEMBERS]->(m:Memory) DETACH DELETE m",
        id=_CHAR_ID,
    )
    await session.run("MATCH (c:Character {id: $id}) DETACH DELETE c", id=_CHAR_ID)


async def run() -> None:
    driver = AsyncGraphDatabase.driver(_BOLT, auth=_AUTH)
    try:
        async with driver.session() as session:
            await _seed_character(session)
            print(f"[seed] Character {_CHAR_ID} created.")

        # Import engine modules after ensuring project is on sys.path
        from npc_engine.engines.memory.memory_engine import MemoryEngine
        from npc_engine.world.time_utils import TimePoint

        game_time = TimePoint(year=1, season="spring", day=5, time_of_day="afternoon")
        engine = MemoryEngine()

        async with driver.session() as session:
            memory_id = await engine.create_from_arousal(
                session,
                character_id=_CHAR_ID,
                arousal=90,
                content=_MEM_CONTENT,
                game_time=game_time,
            )
        print(f"[create] Memory created: {memory_id}")
        assert memory_id is not None, "Memory should have been created for arousal=90"

        # Verify Memory node exists with expected vividness
        async with driver.session() as session:
            result = await session.run(
                "MATCH (c:Character {id: $char_id})-[:REMEMBERS]->(m:Memory {id: $mem_id}) "
                "RETURN toInteger(m.vividness) AS vividness",
                char_id=_CHAR_ID,
                mem_id=memory_id,
            )
            record = await result.single()

        assert record is not None, "Memory node not found in graph"
        initial_vividness = int(record["vividness"])
        print(f"[verify] Memory vividness before decay: {initial_vividness}")
        assert initial_vividness == 80, f"Expected vividness 80, got {initial_vividness}"

        # Trigger vividness decay (simulating a day advance)
        async with driver.session() as session:
            affected = await engine.decay_vividness(session)
        print(f"[decay] Vividness decay ran, {affected} node(s) affected.")
        assert affected >= 1, "At least one Memory node should have been decayed"

        # Verify vividness decreased by default decay (5)
        async with driver.session() as session:
            result = await session.run(
                "MATCH (m:Memory {id: $mem_id}) RETURN toInteger(m.vividness) AS vividness",
                mem_id=memory_id,
            )
            record = await result.single()

        decayed_vividness = int(record["vividness"])
        print(f"[verify] Memory vividness after decay: {decayed_vividness}")
        assert decayed_vividness == initial_vividness - 5, (
            f"Expected vividness {initial_vividness - 5}, got {decayed_vividness}"
        )

        # Cleanup
        async with driver.session() as session:
            await _cleanup(session)
        print("[cleanup] Test nodes removed.")

        print("\n[PASS] scenario_memory_formation completed successfully.")

    finally:
        await driver.close()


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))
    asyncio.run(run())
