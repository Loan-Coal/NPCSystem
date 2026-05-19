"""
add_political_schema.py - Schema migration for Phase 7.2 Political Simulation module.

Creates uniqueness constraints for Title, Agenda, and Leverage nodes.
Backfills power_score=0, treasury=0, military_strength=0 on Faction nodes that
lack these fields (added as optional fields in faction.yaml during Phase 7.0).
Safe to run multiple times (idempotent).

Usage:
    python scripts/migrations/add_political_schema.py
    python scripts/migrations/add_political_schema.py --dry-run

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


CYPHER_CONSTRAINT_TITLE = """
CREATE CONSTRAINT title_id_unique IF NOT EXISTS
FOR (t:Title) REQUIRE t.id IS UNIQUE
"""

CYPHER_CONSTRAINT_AGENDA = """
CREATE CONSTRAINT agenda_id_unique IF NOT EXISTS
FOR (a:Agenda) REQUIRE a.id IS UNIQUE
"""

CYPHER_CONSTRAINT_LEVERAGE = """
CREATE CONSTRAINT leverage_id_unique IF NOT EXISTS
FOR (l:Leverage) REQUIRE l.id IS UNIQUE
"""

CYPHER_COUNT_FACTIONS_MISSING_POWER_SCORE = """
MATCH (f:Faction)
WHERE f.power_score IS NULL
RETURN count(f) AS cnt
"""

CYPHER_BACKFILL_FACTION_FIELDS = """
MATCH (f:Faction)
WHERE f.power_score IS NULL
SET f.power_score = 0,
    f.treasury = coalesce(f.treasury, 0),
    f.military_strength = coalesce(f.military_strength, 0)
RETURN count(f) AS updated
"""


async def run_migration(dry_run: bool = False) -> None:
    """Apply Phase 7.2 schema changes to the graph.

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
            await _backfill_faction_fields(session, dry_run=dry_run, mode=mode)
        print(f"[{mode}] Phase 7.2 political schema migration completed successfully.")
    except Exception as exc:
        print(f"ERROR: Migration failed — {exc}")
        sys.exit(1)
    finally:
        await driver.close()


async def _apply_constraints(session, *, dry_run: bool, mode: str) -> None:
    """Create uniqueness constraints for Phase 7.2 node types.

    Args:
        session: Active Neo4j async session.
        dry_run: When True, only print; do not execute.
        mode: Label string for logging ("DRY-RUN" or "LIVE").
    """
    constraints = [
        ("Title", CYPHER_CONSTRAINT_TITLE),
        ("Agenda", CYPHER_CONSTRAINT_AGENDA),
        ("Leverage", CYPHER_CONSTRAINT_LEVERAGE),
    ]
    for label, cypher in constraints:
        print(f"  [{mode}] CREATE CONSTRAINT {label}.id IS UNIQUE")
        if not dry_run:
            await session.run(cypher)


async def _backfill_faction_fields(session, *, dry_run: bool, mode: str) -> None:
    """Backfill power_score, treasury, military_strength on Faction nodes that lack them.

    Args:
        session: Active Neo4j async session.
        dry_run: When True, only print the count; do not write.
        mode: Label string for logging ("DRY-RUN" or "LIVE").
    """
    result = await session.run(CYPHER_COUNT_FACTIONS_MISSING_POWER_SCORE)
    row = await result.single()
    cnt = row["cnt"] if row else 0

    if cnt == 0:
        print(f"  [{mode}] All Faction nodes already have power_score — nothing to backfill.")
        return

    print(f"  [{mode}] {cnt} Faction node(s) missing power_score — will backfill to 0.")
    if not dry_run:
        result = await session.run(CYPHER_BACKFILL_FACTION_FIELDS)
        row = await result.single()
        updated = row["updated"] if row else 0
        print(f"  [LIVE] Backfilled power_score/treasury/military_strength on {updated} Faction node(s).")
    else:
        print(f"  [DRY-RUN] Would backfill {cnt} Faction node(s). No changes made.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run_migration(dry_run=dry_run))
