"""
scenario_beliefs.py - E2E scenario for Feature 3.4: Belief nodes.

Requires: live Neo4j instance.
Run with: python e2e/scenarios/scenario_beliefs.py

Steps:
  1. Seed a Character node.
  2. Create two beliefs via create_belief.
  3. Fetch beliefs and assert content + confidence (sorted by confidence desc).
  4. Update confidence on one belief.
  5. Cleanup.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

_BOLT = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))

_CHAR_ID = f"e2e_belief_char_{uuid.uuid4().hex[:8]}"


async def run() -> None:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(_BOLT, auth=_AUTH)

    from npc_engine.graph.belief_service import (
        create_belief,
        get_beliefs_for_character_svc,
        update_confidence,
    )
    from npc_engine.world.time_utils import TimePoint

    game_time = TimePoint(year=1, season="summer", day=10, time_of_day="midday")

    try:
        # Step 1: seed character
        async with driver.session() as session:
            await session.run(
                "MERGE (c:Character {id: $id}) SET c.name = 'E2E NPC', c.is_active = true",
                id=_CHAR_ID,
            )
        print(f"[seed] Character {_CHAR_ID} created.")

        # Step 2: create two beliefs
        async with driver.session() as session:
            belief_id_1 = await create_belief(
                session,
                character_id=_CHAR_ID,
                content="The merchants guild cannot be trusted.",
                confidence=85,
                game_time=game_time,
            )
            belief_id_2 = await create_belief(
                session,
                character_id=_CHAR_ID,
                content="Rain in summer is a bad omen.",
                confidence=60,
                game_time=game_time,
            )
        print(f"[create] Belief 1: {belief_id_1} | Belief 2: {belief_id_2}")

        # Step 3: fetch and assert
        async with driver.session() as session:
            beliefs = await get_beliefs_for_character_svc(session, character_id=_CHAR_ID, k=5)

        assert len(beliefs) == 2, f"Expected 2 beliefs, got {len(beliefs)}"
        assert beliefs[0]["confidence"] >= beliefs[1]["confidence"], "Expected descending confidence order"
        assert beliefs[0]["id"] == belief_id_1, "Highest-confidence belief should be first"
        print(f"[verify] Beliefs fetched and ordered correctly. Top confidence: {beliefs[0]['confidence']}")

        # Step 4: update confidence
        async with driver.session() as session:
            await update_confidence(session, belief_id=belief_id_2, new_confidence=90)

        async with driver.session() as session:
            beliefs_updated = await get_beliefs_for_character_svc(session, character_id=_CHAR_ID, k=5)

        updated = next(b for b in beliefs_updated if b["id"] == belief_id_2)
        assert updated["confidence"] == 90, f"Expected confidence 90, got {updated['confidence']}"
        print(f"[verify] Confidence updated to {updated['confidence']} for belief {belief_id_2}.")

        # Cleanup
        async with driver.session() as session:
            await session.run(
                "MATCH (c:Character {id: $id})-[:BELIEVES]->(b:Belief) DETACH DELETE b",
                id=_CHAR_ID,
            )
            await session.run("MATCH (c:Character {id: $id}) DETACH DELETE c", id=_CHAR_ID)
        print("[cleanup] Test nodes removed.")

        print("\n[PASS] scenario_beliefs completed successfully.")

    finally:
        await driver.close()


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))
    asyncio.run(run())
