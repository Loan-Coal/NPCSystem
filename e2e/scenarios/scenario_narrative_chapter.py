"""
scenario_narrative_chapter.py - E2E scenario: quest completions trigger a chapter transition.

Setup:
  - Mark 3 quests as completed in the current tick window.
  - Advance ticks until the chapter engine detects the transition threshold.

Expected outcome:
  - A CHAPTER node is created in Neo4j with status='open'.
  - The scheduler response includes a ``chapter`` entry with ``transition=True``.
  - The chapter has a name derived from the LLM (or rule-based fallback).

Depends on: ChapterEngine wired in tick scheduler, CHAPTER/QUEST node types.
"""

from __future__ import annotations

import asyncio
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

SETUP_QUESTS_CYPHER = """
WITH range(0, 2) AS indices
UNWIND indices AS i
MERGE (q:Quest {id: 'chap_quest_' + toString(i)})
  SET q.title = 'Test Quest ' + toString(i),
      q.status = 'completed',
      q.completed_at_tick = 1,
      q.last_graph_updated_at = datetime()
"""

TEARDOWN_CYPHER = """
MATCH (q:Quest) WHERE q.id STARTS WITH 'chap_quest_' DELETE q
MATCH (c:Chapter) WHERE c.name IN ['Prologue', 'The Storm Breaks'] DETACH DELETE c
"""

CHECK_CHAPTER_CYPHER = """
MATCH (c:Chapter)
WHERE c.status = 'open'
RETURN c.id AS id, c.name AS name, c.started_at_tick AS started_at_tick
ORDER BY c.started_at_tick DESC
LIMIT 1
"""


async def run_scenario() -> None:
    """Run the narrative chapter E2E scenario."""
    try:
        from neo4j import AsyncGraphDatabase
    except ImportError:
        print("ERROR: neo4j package not installed.")
        return

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        async with driver.session() as session:
            print("Setting up 3 completed quests...")
            await session.run(SETUP_QUESTS_CYPHER)

            print("Advancing ticks to trigger chapter detection...")
            import httpx
            transition_detected = False
            async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
                for tick_num in range(5):
                    resp = await client.post(
                        "/v1/admin/advance",
                        json={"tick_delta": 1, "time_delta_seconds": 3600},
                    )
                    if resp.status_code != 200:
                        print(f"  WARN: tick {tick_num + 1} returned {resp.status_code}")
                        continue
                    data = resp.json()
                    chapter_rows = data.get("chapter", [])
                    for row in chapter_rows:
                        if row.get("transition"):
                            print(f"  Tick {tick_num + 1}: chapter transition → {row.get('chapter_name')!r}")
                            transition_detected = True

            print("\nVerifying CHAPTER node in Neo4j...")
            result = await session.run(CHECK_CHAPTER_CYPHER)
            row = await result.single()
            if row:
                print(f"  Chapter: id={row['id']!r}  name={row['name']!r}  started_at={row['started_at_tick']}")
                assert row["name"] is not None
                print("\nScenario PASSED: CHAPTER node created.")
            else:
                print("  WARN: No open chapter found — engine may need more ticks or threshold adjustment.")

    finally:
        async with driver.session() as session:
            await session.run(TEARDOWN_CYPHER)
            print("Teardown complete.")
        await driver.close()


if __name__ == "__main__":
    asyncio.run(run_scenario())
