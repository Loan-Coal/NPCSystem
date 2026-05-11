"""
add_faction_support.py - Idempotent migration: add Faction node constraints.

Creates a uniqueness constraint on Faction.id if it does not already exist.
Safe to run multiple times (all operations are idempotent).

Usage:
    python scripts/migrations/add_faction_support.py
    NEO4J_URI=bolt://localhost:7687 python scripts/migrations/add_faction_support.py

Does NOT: migrate existing Character.faction string fields to MEMBER_OF edges.
          That migration requires game-specific data and is deferred to operators.

Dependencies injected: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import asyncio
import os
import sys


async def run_migration() -> None:
    """Apply Faction node constraints to the graph database."""
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

    print(f"Connecting to Neo4j at {uri} ...")
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    try:
        async with driver.session() as session:
            await _create_faction_constraint(session)
            await _verify_faction_constraint(session)
        print("Migration completed successfully.")
    finally:
        await driver.close()


async def _create_faction_constraint(session) -> None:
    """Create uniqueness constraint on Faction.id (idempotent)."""
    print("  Creating Faction.id uniqueness constraint ...")
    try:
        await session.run(
            "CREATE CONSTRAINT faction_id_unique IF NOT EXISTS "
            "FOR (f:Faction) REQUIRE f.id IS UNIQUE"
        )
        print("  Constraint created (or already existed).")
    except Exception as exc:  # noqa: BLE001
        # Older Neo4j versions use different syntax — try the legacy form
        try:
            await session.run(
                "CREATE CONSTRAINT ON (f:Faction) ASSERT f.id IS UNIQUE"
            )
            print("  Constraint created via legacy syntax.")
        except Exception:  # noqa: BLE001
            print(f"  WARNING: Could not create constraint: {exc}")
            print("  Continuing — constraint may already exist under a different name.")


async def _verify_faction_constraint(session) -> None:
    """Check that the constraint is present and log the result."""
    print("  Verifying constraints ...")
    result = await session.run("SHOW CONSTRAINTS")
    constraints = [record.data() async for record in result]
    faction_constraints = [
        c for c in constraints
        if "Faction" in str(c) or "faction" in str(c).lower()
    ]
    if faction_constraints:
        print(f"  Found {len(faction_constraints)} Faction constraint(s).")
    else:
        print("  WARNING: No Faction constraints found — verify manually.")


if __name__ == "__main__":
    asyncio.run(run_migration())
