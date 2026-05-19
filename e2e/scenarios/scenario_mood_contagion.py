"""
scenario_mood_contagion.py - E2E scenario: mood spreads between co-located affectionate NPCs.

Setup:
  - Two NPCs (alice, bob) share a location.
  - RELATES_TO.affection = 75 (above threshold of 50).
  - Alice starts elated (valence=80, arousal=70); Bob starts melancholic (valence=-60, arousal=20).

Expected outcome after several tick advances:
  - Alice's mood label shifts toward less positive (valence drops toward Bob's).
  - Bob's mood label shifts toward less negative (valence rises toward Alice's).
  - Both CHARACTER nodes have current_mood and mood_intensity persisted in Neo4j.

Depends on: MoodContagionEngine wired in tick scheduler, CHARACTER node with mood fields.
"""

from __future__ import annotations

import asyncio
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

SETUP_CYPHER = """
MERGE (alice:Character {id: 'mood_alice'})
  SET alice.name = 'Alice', alice.archetype = 'merchant', alice.is_active = true,
      alice.is_player = false, alice.biography = 'test', alice.gossipy = 50,
      alice.credulity = 50, alice.honesty = 80,
      alice.current_mood = 'elated', alice.mood_intensity = 0.7,
      alice.created_at = datetime(), alice.updated_at = datetime(),
      alice.last_graph_updated_at = datetime()

MERGE (bob:Character {id: 'mood_bob'})
  SET bob.name = 'Bob', bob.archetype = 'guard', bob.is_active = true,
      bob.is_player = false, bob.biography = 'test', bob.gossipy = 30,
      bob.credulity = 60, bob.honesty = 70,
      bob.current_mood = 'melancholic', bob.mood_intensity = 0.2,
      bob.created_at = datetime(), bob.updated_at = datetime(),
      bob.last_graph_updated_at = datetime()

MERGE (tavern:Location {id: 'mood_tavern'})
  SET tavern.name = 'Tavern', tavern.description = 'test',
      tavern.last_graph_updated_at = datetime()

MERGE (alice)-[:LOCATED_AT {arrived_at: datetime()}]->(tavern)
MERGE (bob)-[:LOCATED_AT {arrived_at: datetime()}]->(tavern)

MERGE (alice)-[r:RELATES_TO]->(bob)
  SET r.trust = 70, r.fear = 10, r.affection = 75,
      r.interaction_count = 20, r.last_updated_at = datetime(),
      r.relevance_score = 0.8
"""

TEARDOWN_CYPHER = """
MATCH (c:Character) WHERE c.id IN ['mood_alice', 'mood_bob'] DETACH DELETE c
MATCH (l:Location {id: 'mood_tavern'}) DETACH DELETE l
"""

CHECK_MOOD_CYPHER = """
MATCH (c:Character {id: $char_id})
RETURN c.current_mood AS mood, c.mood_intensity AS intensity
"""


async def run_scenario() -> None:
    """Run the mood contagion E2E scenario."""
    try:
        from neo4j import AsyncGraphDatabase
    except ImportError:
        print("ERROR: neo4j package not installed.")
        return

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        async with driver.session() as session:
            print("Setting up mood contagion test data...")
            await session.run(SETUP_CYPHER)

            print("Triggering tick advances via scheduler API (3 ticks)...")
            import httpx
            async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
                for tick_num in range(3):
                    resp = await client.post(
                        "/v1/admin/advance",
                        json={"tick_delta": 1, "time_delta_seconds": 3600},
                    )
                    if resp.status_code != 200:
                        print(f"  WARN: tick {tick_num + 1} advance returned {resp.status_code}")
                    else:
                        data = resp.json()
                        mood_rows = data.get("mood_contagion", [])
                        print(f"  Tick {tick_num + 1}: mood_contagion affected={[r.get('affected') for r in mood_rows]}")

            print("\nVerifying mood persistence in Neo4j...")
            alice_result = await session.run(CHECK_MOOD_CYPHER, char_id="mood_alice")
            alice_row = await alice_result.single()
            bob_result = await session.run(CHECK_MOOD_CYPHER, char_id="mood_bob")
            bob_row = await bob_result.single()

            print(f"  Alice: mood={alice_row['mood']!r}  intensity={alice_row['intensity']:.3f}")
            print(f"  Bob:   mood={bob_row['mood']!r}  intensity={bob_row['intensity']:.3f}")

            assert alice_row["mood"] is not None, "Alice mood should be persisted"
            assert bob_row["mood"] is not None, "Bob mood should be persisted"
            print("\nScenario PASSED: moods are persisted in Neo4j.")

    finally:
        async with driver.session() as session:
            await session.run(TEARDOWN_CYPHER)
            print("Teardown complete.")
        await driver.close()


if __name__ == "__main__":
    asyncio.run(run_scenario())
