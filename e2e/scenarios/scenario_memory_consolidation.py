"""
scenario_memory_consolidation.py - E2E scenario for Feature 3.3: Memory consolidation engine.

Requires: live Neo4j instance.
Run with: python e2e/scenarios/scenario_memory_consolidation.py

Steps:
  1. Seed a Character node.
  2. Seed a SessionStore with 15 mock dialogue turns.
  3. Call MemoryConsolidationEngine.consolidate with a mock LLM adapter.
  4. Assert a Memory node now exists for the character in Neo4j.
  5. Cleanup.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock

_BOLT = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))

_CHAR_ID = f"e2e_consol_char_{uuid.uuid4().hex[:8]}"
_MOCK_SUMMARY = "I met the traveller who warned me about the bandits on the northern road."


def _make_mock_llm() -> MagicMock:
    llm = MagicMock()
    llm.generate = AsyncMock(return_value=_MOCK_SUMMARY)
    return llm


async def run() -> None:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(_BOLT, auth=_AUTH)

    # Use import after sys.path is set
    from npc_engine.engines.dialogue.session_store import SessionStore
    from npc_engine.engines.memory_consolidation.memory_consolidation_engine import (
        MemoryConsolidationEngine,
    )
    from npc_engine.world.time_utils import TimePoint

    try:
        # Step 1: seed character
        async with driver.session() as session:
            await session.run(
                "MERGE (c:Character {id: $id}) SET c.name = 'E2E NPC', c.is_active = true",
                id=_CHAR_ID,
            )
        print(f"[seed] Character {_CHAR_ID} created.")

        # Step 2: seed session store with 15 turns
        store = SessionStore(ttl_seconds=3600, max_turns=100)
        turns = [f"Player said: hello number {i}. NPC replied: indeed {i}." for i in range(15)]
        store.append_turns(player_id="player_e2e", npc_id=_CHAR_ID, new_turns=turns)
        assert len(store.get_all_turns_for_npc(_CHAR_ID)) == 15
        print(f"[seed] SessionStore seeded with {len(turns)} turns.")

        # Step 3: build engine with mock LLM and call consolidate
        llm = _make_mock_llm()
        engine = MemoryConsolidationEngine(
            session_store=store,
            llm_client=llm,
            turn_threshold=10,
        )
        game_time = TimePoint(year=1, season="summer", day=3, time_of_day="morning")

        async with driver.session() as session:
            memory_id = await engine.consolidate(session, npc_id=_CHAR_ID, game_time=game_time)

        print(f"[consolidate] Memory created: {memory_id}")
        assert memory_id is not None, "Expected a memory_id but got None"

        # Step 4: verify Memory node exists in Neo4j
        async with driver.session() as session:
            result = await session.run(
                "MATCH (c:Character {id: $char_id})-[:REMEMBERS]->(m:Memory {id: $mem_id}) "
                "RETURN m.content AS content, toInteger(m.vividness) AS vividness",
                char_id=_CHAR_ID,
                mem_id=memory_id,
            )
            record = await result.single()

        assert record is not None, "Memory node not found in graph"
        assert record["content"] == _MOCK_SUMMARY, f"Unexpected content: {record['content']}"
        assert record["vividness"] == 75, f"Expected vividness 75, got {record['vividness']}"
        print(f"[verify] Memory vividness={record['vividness']}, content OK.")

        # Cleanup
        async with driver.session() as session:
            await session.run(
                "MATCH (c:Character {id: $id})-[:REMEMBERS]->(m:Memory) DETACH DELETE m",
                id=_CHAR_ID,
            )
            await session.run("MATCH (c:Character {id: $id}) DETACH DELETE c", id=_CHAR_ID)
        print("[cleanup] Test nodes removed.")

        print("\n[PASS] scenario_memory_consolidation completed successfully.")

    finally:
        await driver.close()


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))
    asyncio.run(run())
