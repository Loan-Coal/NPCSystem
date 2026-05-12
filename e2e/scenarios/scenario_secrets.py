"""
scenario_secrets.py - E2E scenario for Feature 3.7: Secret nodes.

Requires: live Neo4j instance.
Run with: python e2e/scenarios/scenario_secrets.py

Steps:
  1. Seed a Character node.
  2. Create a secret for that character.
  3. Fetch secrets, assert one returned with correct severity.
  4. Cleanup.
"""

from __future__ import annotations

import asyncio
import os
import uuid

_BOLT = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))

_CHAR_ID = f"e2e_secret_char_{uuid.uuid4().hex[:8]}"


async def run() -> None:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(_BOLT, auth=_AUTH)

    from npc_engine.graph.secret_service import (
        create_secret,
        get_secrets_for_character_svc,
    )
    from npc_engine.world.time_utils import TimePoint

    game_time = TimePoint(year=3, season="summer", day=7, time_of_day="evening")
    secret_id: str = ""

    try:
        # Step 1: seed character
        async with driver.session() as session:
            await session.run(
                "MERGE (c:Character {id: $id}) SET c.name = 'E2E Secret Keeper', c.is_active = true",
                id=_CHAR_ID,
            )
        print(f"[seed] Character {_CHAR_ID} created.")

        # Step 2: create a secret
        async with driver.session() as session:
            secret_id = await create_secret(
                session,
                character_id=_CHAR_ID,
                content="The duke is planning to poison the king.",
                severity=90,
                game_time=game_time,
            )
        print(f"[create] Secret {secret_id} created for {_CHAR_ID}.")

        # Step 3: fetch secrets — expect one with severity 90
        async with driver.session() as session:
            secrets = await get_secrets_for_character_svc(session, character_id=_CHAR_ID)

        assert len(secrets) == 1, f"Expected 1 secret, got {len(secrets)}"
        assert secrets[0]["severity"] == 90, f"Expected severity 90, got {secrets[0]['severity']}"
        assert "duke" in secrets[0]["content"].lower(), "Content mismatch"
        print(f"[assert] 1 secret returned with severity 90. OK.")

        print("\nAll assertions passed. Feature 3.7 E2E scenario: PASS")

    finally:
        # Cleanup
        async with driver.session() as session:
            await session.run(
                "MATCH (c:Character {id: $id}) DETACH DELETE c",
                id=_CHAR_ID,
            )
            if secret_id:
                await session.run(
                    "MATCH (s:Secret {id: $id}) DETACH DELETE s",
                    id=secret_id,
                )
        await driver.close()
        print("[cleanup] Nodes removed.")


if __name__ == "__main__":
    asyncio.run(run())
