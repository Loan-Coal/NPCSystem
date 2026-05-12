"""
scenario_goals.py - E2E scenario for Feature 3.5: Goal nodes.

Requires: live Neo4j instance.
Run with: python e2e/scenarios/scenario_goals.py

Steps:
  1. Seed a Character node.
  2. Create two goals: one active, one achieved.
  3. Fetch active goals and assert only one returned.
  4. Update the active goal's status to achieved.
  5. Fetch active goals again and assert empty.
  6. Cleanup.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

_BOLT = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))

_CHAR_ID = f"e2e_goal_char_{uuid.uuid4().hex[:8]}"


async def run() -> None:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(_BOLT, auth=_AUTH)

    from npc_engine.graph.goal_service import (
        create_goal,
        get_goals_for_character_svc,
        update_goal_status,
    )
    from npc_engine.world.time_utils import TimePoint

    game_time = TimePoint(year=1, season="summer", day=5, time_of_day="morning")

    try:
        # Step 1: seed character
        async with driver.session() as session:
            await session.run(
                "MERGE (c:Character {id: $id}) SET c.name = 'E2E NPC', c.is_active = true",
                id=_CHAR_ID,
            )
        print(f"[seed] Character {_CHAR_ID} created.")

        # Step 2: create one active and one already-achieved goal
        async with driver.session() as session:
            goal_id_active = await create_goal(
                session,
                character_id=_CHAR_ID,
                description="Find the stolen amulet.",
                urgency=80,
                game_time=game_time,
            )

        # Create an achieved goal by creating active then patching status
        async with driver.session() as session:
            goal_id_achieved = await create_goal(
                session,
                character_id=_CHAR_ID,
                description="Deliver the message to the mayor.",
                urgency=40,
                game_time=game_time,
            )
        async with driver.session() as session:
            await update_goal_status(session, goal_id=goal_id_achieved, new_status="achieved")

        print(f"[create] Active goal: {goal_id_active} | Achieved goal: {goal_id_achieved}")

        # Step 3: fetch active goals — should return only 1
        async with driver.session() as session:
            active_goals = await get_goals_for_character_svc(
                session, character_id=_CHAR_ID, k=10, status_filter="active"
            )

        assert len(active_goals) == 1, f"Expected 1 active goal, got {len(active_goals)}"
        assert active_goals[0]["id"] == goal_id_active
        assert active_goals[0]["status"] == "active"
        print(f"[verify] One active goal returned: {active_goals[0]['description']}")

        # Step 4: update the active goal to achieved
        async with driver.session() as session:
            await update_goal_status(session, goal_id=goal_id_active, new_status="achieved")
        print(f"[update] Goal {goal_id_active} marked as achieved.")

        # Step 5: fetch active goals again — should be empty
        async with driver.session() as session:
            active_goals_after = await get_goals_for_character_svc(
                session, character_id=_CHAR_ID, k=10, status_filter="active"
            )

        assert len(active_goals_after) == 0, (
            f"Expected 0 active goals after update, got {len(active_goals_after)}"
        )
        print("[verify] No active goals remain after update.")

        # Cleanup
        async with driver.session() as session:
            await session.run(
                "MATCH (c:Character {id: $id})-[:PURSUES]->(g:Goal) DETACH DELETE g",
                id=_CHAR_ID,
            )
            await session.run("MATCH (c:Character {id: $id}) DETACH DELETE c", id=_CHAR_ID)
        print("[cleanup] Test nodes removed.")

        print("\n[PASS] scenario_goals completed successfully.")

    finally:
        await driver.close()


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))
    asyncio.run(run())
