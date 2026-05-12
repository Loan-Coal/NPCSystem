"""
scenario_items.py - E2E scenario for Feature 3.6: Item nodes and ownership.

Requires: live Neo4j instance.
Run with: python e2e/scenarios/scenario_items.py

Steps:
  1. Seed two Character nodes.
  2. Create an item owned by character 1.
  3. Fetch items for character 1 and assert one returned.
  4. Transfer ownership to character 2.
  5. Fetch items for character 1 and assert empty.
  6. Fetch items for character 2 and assert one returned.
  7. Cleanup.
"""

from __future__ import annotations

import asyncio
import os
import uuid

_BOLT = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))

_CHAR1_ID = f"e2e_item_char1_{uuid.uuid4().hex[:8]}"
_CHAR2_ID = f"e2e_item_char2_{uuid.uuid4().hex[:8]}"


async def run() -> None:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(_BOLT, auth=_AUTH)

    from npc_engine.graph.item_service import (
        create_item,
        get_items_for_character_svc,
        transfer_ownership,
    )
    from npc_engine.world.time_utils import TimePoint

    game_time = TimePoint(year=1, season="autumn", day=10, time_of_day="afternoon")

    try:
        # Step 1: seed two characters
        async with driver.session() as session:
            await session.run(
                "MERGE (c:Character {id: $id}) SET c.name = 'E2E NPC One', c.is_active = true",
                id=_CHAR1_ID,
            )
            await session.run(
                "MERGE (c:Character {id: $id}) SET c.name = 'E2E NPC Two', c.is_active = true",
                id=_CHAR2_ID,
            )
        print(f"[seed] Characters {_CHAR1_ID} and {_CHAR2_ID} created.")

        # Step 2: create item owned by character 1
        async with driver.session() as session:
            item_id = await create_item(
                session,
                character_id=_CHAR1_ID,
                name="Ancient Compass",
                description="Points toward hidden treasure.",
                value=200,
                rarity="rare",
                type_="misc",
                is_unique=True,
                game_time=game_time,
            )
        print(f"[create] Item {item_id} created and assigned to {_CHAR1_ID}.")

        # Step 3: fetch items for character 1 — expect one
        async with driver.session() as session:
            items_1 = await get_items_for_character_svc(session, character_id=_CHAR1_ID)
        assert len(items_1) == 1, f"Expected 1 item for char1, got {len(items_1)}"
        assert items_1[0]["name"] == "Ancient Compass"
        print(f"[assert] Character 1 owns 1 item. OK.")

        # Step 4: transfer ownership to character 2
        async with driver.session() as session:
            await transfer_ownership(
                session,
                item_id=item_id,
                from_character_id=_CHAR1_ID,
                to_character_id=_CHAR2_ID,
                game_time=game_time,
            )
        print(f"[transfer] Item {item_id} transferred to {_CHAR2_ID}.")

        # Step 5: fetch items for character 1 — expect empty
        async with driver.session() as session:
            items_1_after = await get_items_for_character_svc(session, character_id=_CHAR1_ID)
        assert len(items_1_after) == 0, f"Expected 0 items for char1 after transfer, got {len(items_1_after)}"
        print("[assert] Character 1 owns 0 items after transfer. OK.")

        # Step 6: fetch items for character 2 — expect one
        async with driver.session() as session:
            items_2 = await get_items_for_character_svc(session, character_id=_CHAR2_ID)
        assert len(items_2) == 1, f"Expected 1 item for char2, got {len(items_2)}"
        assert items_2[0]["name"] == "Ancient Compass"
        print("[assert] Character 2 owns 1 item. OK.")

        print("\nAll assertions passed. Feature 3.6 E2E scenario: PASS")

    finally:
        # Cleanup
        async with driver.session() as session:
            await session.run(
                "MATCH (c:Character) WHERE c.id IN [$c1, $c2] DETACH DELETE c",
                c1=_CHAR1_ID,
                c2=_CHAR2_ID,
            )
            await session.run(
                "MATCH (i:Item {id: $id}) DETACH DELETE i",
                id=item_id if "item_id" in dir() else "",
            )
        await driver.close()
        print("[cleanup] Nodes removed.")


if __name__ == "__main__":
    asyncio.run(run())
