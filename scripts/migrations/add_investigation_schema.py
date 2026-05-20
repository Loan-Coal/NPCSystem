"""
add_investigation_schema.py - Schema migration for Phase 7.1 Detective/Mystery module.

Creates uniqueness constraints for Evidence and Deduction nodes.
Safe to run multiple times (CREATE CONSTRAINT IF NOT EXISTS is idempotent).

Usage:
    python scripts/migrations/add_investigation_schema.py
    python scripts/migrations/add_investigation_schema.py --dry-run

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


CYPHER_CONSTRAINT_EVIDENCE = """
CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS
FOR (e:Evidence) REQUIRE e.id IS UNIQUE
"""

CYPHER_CONSTRAINT_DEDUCTION = """
CREATE CONSTRAINT deduction_id_unique IF NOT EXISTS
FOR (d:Deduction) REQUIRE d.id IS UNIQUE
"""


async def run_migration(dry_run: bool = False) -> None:
    """Apply Phase 7.1 schema changes to the graph.

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
        print(f"[{mode}] Phase 7.1 investigation schema migration completed successfully.")
    except Exception as exc:
        print(f"ERROR: Migration failed — {exc}")
        sys.exit(1)
    finally:
        await driver.close()


async def _apply_constraints(session, *, dry_run: bool, mode: str) -> None:
    """Create uniqueness constraints for Phase 7.1 node types.

    Args:
        session: Active Neo4j async session.
        dry_run: When True, only print; do not execute.
        mode: Label string for logging ("DRY-RUN" or "LIVE").
    """
    constraints = [
        ("Evidence", CYPHER_CONSTRAINT_EVIDENCE),
        ("Deduction", CYPHER_CONSTRAINT_DEDUCTION),
    ]
    for label, cypher in constraints:
        print(f"  [{mode}] CREATE CONSTRAINT {label}.id IS UNIQUE")
        if not dry_run:
            await session.run(cypher)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run_migration(dry_run=dry_run))
