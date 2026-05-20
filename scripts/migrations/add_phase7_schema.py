"""
add_phase7_schema.py - Schema migration for Phase 7 M/S modules.

Creates constraints for CHAPTER, CHOICE, and NARRATIVE_BEAT nodes.
Backfills is_canonical=false on all existing EVENT nodes that lack the field.
Safe to run multiple times (MERGE/SET are idempotent).

Usage:
    python scripts/migrations/add_phase7_schema.py
    python scripts/migrations/add_phase7_schema.py --dry-run

Options:
    --dry-run   Print planned changes without writing to the graph.

Exit codes:
    0  Migration complete (or dry-run complete).
    1  Connection or migration error.

Dependencies injected: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import asyncio
import os
import sys


CYPHER_CONSTRAINT_CHAPTER = """
CREATE CONSTRAINT chapter_id_unique IF NOT EXISTS
FOR (c:Chapter) REQUIRE c.id IS UNIQUE
"""

CYPHER_CONSTRAINT_CHOICE = """
CREATE CONSTRAINT choice_id_unique IF NOT EXISTS
FOR (c:Choice) REQUIRE c.id IS UNIQUE
"""

CYPHER_CONSTRAINT_NARRATIVE_BEAT = """
CREATE CONSTRAINT narrative_beat_id_unique IF NOT EXISTS
FOR (n:NarrativeBeat) REQUIRE n.id IS UNIQUE
"""

CYPHER_COUNT_EVENTS_WITHOUT_CANONICAL = """
MATCH (e:Event)
WHERE e.is_canonical IS NULL
RETURN count(e) AS cnt
"""

CYPHER_BACKFILL_IS_CANONICAL = """
MATCH (e:Event)
WHERE e.is_canonical IS NULL
SET e.is_canonical = false
RETURN count(e) AS updated
"""


async def run_migration(dry_run: bool = False) -> None:
    """Apply Phase 7 M/S schema changes to the graph.

    Args:
        dry_run: When True, print planned changes without writing to the graph.
    """
    try:
        from neo4j import AsyncGraphDatabase
    except ImportError:
        print("ERROR: neo4j package not installed. Run: pip install neo4j")
        sys.exit(1)

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")

    if not password:
        print("ERROR: NEO4J_PASSWORD env var is required")
        sys.exit(1)

    mode = "DRY-RUN" if dry_run else "LIVE"
    print(f"[{mode}] Connecting to Neo4j at {uri} ...")
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    try:
        async with driver.session() as session:
            await _apply_constraints(session, dry_run=dry_run, mode=mode)
            await _backfill_is_canonical(session, dry_run=dry_run, mode=mode)

        print(f"[{mode}] Phase 7 schema migration completed successfully.")
    except Exception as exc:
        print(f"ERROR: Migration failed — {exc}")
        sys.exit(1)
    finally:
        await driver.close()


async def _apply_constraints(session, *, dry_run: bool, mode: str) -> None:
    """Create uniqueness constraints for Phase 7 node types.

    Args:
        session: Active Neo4j async session.
        dry_run: When True, only print; do not execute.
        mode: Label string for logging ("DRY-RUN" or "LIVE").
    """
    constraints = [
        ("Chapter", CYPHER_CONSTRAINT_CHAPTER),
        ("Choice", CYPHER_CONSTRAINT_CHOICE),
        ("NarrativeBeat", CYPHER_CONSTRAINT_NARRATIVE_BEAT),
    ]
    for label, cypher in constraints:
        print(f"  [{mode}] CREATE CONSTRAINT {label}.id IS UNIQUE")
        if not dry_run:
            await session.run(cypher)


async def _backfill_is_canonical(session, *, dry_run: bool, mode: str) -> None:
    """Backfill is_canonical=false on EVENT nodes that lack the field.

    Args:
        session: Active Neo4j async session.
        dry_run: When True, only print the count; do not write.
        mode: Label string for logging ("DRY-RUN" or "LIVE").
    """
    result = await session.run(CYPHER_COUNT_EVENTS_WITHOUT_CANONICAL)
    row = await result.single()
    cnt = row["cnt"] if row else 0

    if cnt == 0:
        print(f"  [{mode}] All EVENT nodes already have is_canonical set — nothing to backfill.")
        return

    print(f"  [{mode}] {cnt} EVENT node(s) missing is_canonical — will backfill to false.")
    if not dry_run:
        result = await session.run(CYPHER_BACKFILL_IS_CANONICAL)
        row = await result.single()
        updated = row["updated"] if row else 0
        print(f"  [LIVE] Backfilled is_canonical=false on {updated} EVENT node(s).")
    else:
        print(f"  [DRY-RUN] Would set is_canonical=false on {cnt} EVENT node(s). No changes made.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run_migration(dry_run=dry_run))
