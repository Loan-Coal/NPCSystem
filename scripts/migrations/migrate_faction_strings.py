"""
migrate_faction_strings.py - Migrate Character.faction string fields to MEMBER_OF edges.

Reads all Character nodes with a non-null `faction` string property, looks up the
matching Faction node by id, and creates a MEMBER_OF edge if one does not already exist.

Safe to run multiple times (MERGE is idempotent).

Usage:
    python scripts/migrations/migrate_faction_strings.py
    python scripts/migrations/migrate_faction_strings.py --dry-run

Options:
    --dry-run   Print what would change without writing anything to the graph.

Exit codes:
    0  All characters migrated (or dry-run complete).
    1  One or more characters reference a faction_id with no matching Faction node.
       No writes are performed when any unresolvable faction is found (fail-fast).

Dependencies injected: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import asyncio
import os
import sys


CYPHER_FIND_UNMIGRATED = """
MATCH (c:Character)
WHERE c.faction IS NOT NULL
  AND NOT (c)-[:MEMBER_OF]->(:Faction)
RETURN c.id AS character_id, c.faction AS faction_string
ORDER BY c.id
"""

CYPHER_CHECK_FACTION_EXISTS = """
MATCH (f:Faction {id: $faction_id})
RETURN f.id AS faction_id
LIMIT 1
"""

CYPHER_CREATE_MEMBER_OF = """
MATCH (c:Character {id: $character_id}), (f:Faction {id: $faction_id})
MERGE (c)-[r:MEMBER_OF]->(f)
ON CREATE SET r.role = 'member', r.status = 'active', r.joined_at_tick = 0,
              r.created_by_migration = $migration_id
RETURN r
"""


async def run_migration(dry_run: bool = False) -> None:
    """Migrate Character.faction string fields to MEMBER_OF edges.

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
            candidates = await _find_unmigrated(session)
            if not candidates:
                print(f"[{mode}] No unmigrated characters found — nothing to do.")
                return

            print(f"[{mode}] Found {len(candidates)} character(s) with unlinked faction strings.")

            missing_factions = await _check_factions_exist(session, candidates)
            if missing_factions:
                print("ERROR: The following faction IDs have no matching Faction node:")
                for faction_id in sorted(missing_factions):
                    affected = [c for c in candidates if c["faction_string"] == faction_id]
                    char_ids = ", ".join(c["character_id"] for c in affected)
                    print(f"  faction_id={faction_id!r}  characters={char_ids}")
                print("Create the Faction node(s) first, then re-run this script.")
                sys.exit(1)

            for row in candidates:
                char_id = row["character_id"]
                faction_id = row["faction_string"]
                print(f"  {char_id} → MEMBER_OF → {faction_id}")
                if not dry_run:
                    await _create_member_of(session, char_id, faction_id)

            if dry_run:
                print(f"[DRY-RUN] {len(candidates)} edge(s) would be created. No changes made.")
            else:
                print(f"[LIVE] {len(candidates)} MEMBER_OF edge(s) created.")

        print("Migration completed successfully.")
    finally:
        await driver.close()


async def _find_unmigrated(session) -> list[dict]:
    """Return characters with a faction string but no MEMBER_OF edge.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of dicts with keys ``character_id`` and ``faction_string``.
    """
    result = await session.run(CYPHER_FIND_UNMIGRATED)
    return [{"character_id": rec["character_id"], "faction_string": rec["faction_string"]}
            async for rec in result]


async def _check_factions_exist(session, candidates: list[dict]) -> set[str]:
    """Return the set of faction_id strings that have no matching Faction node.

    Args:
        session: Active Neo4j async session.
        candidates: List of dicts from ``_find_unmigrated``.

    Returns:
        Set of unresolvable faction ID strings (empty set means all factions exist).
    """
    unique_faction_ids = {row["faction_string"] for row in candidates}
    missing: set[str] = set()
    for faction_id in unique_faction_ids:
        result = await session.run(CYPHER_CHECK_FACTION_EXISTS, faction_id=faction_id)
        record = await result.single()
        if record is None:
            missing.add(faction_id)
    return missing


async def _create_member_of(session, character_id: str, faction_id: str) -> None:
    """Create a MEMBER_OF edge between a Character and a Faction.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.
        faction_id: ID of the target Faction node.
    """
    await session.run(
        CYPHER_CREATE_MEMBER_OF,
        character_id=character_id,
        faction_id=faction_id,
        migration_id=MIGRATION_ID,
    )


# ---------------------------------------------------------------------------
# R5.4 migration contract — identity, claimed fields, and the down path.
# ---------------------------------------------------------------------------

MIGRATION_ID = "migrate_faction_strings"
MIGRATES = []
REVERSIBLE = "partial"
IRREVERSIBLE_REASON = (
    "down() deletes only MEMBER_OF edges this migration stamped with "
    "created_by_migration, so memberships created by gameplay are never touched. Edges "
    "written by the pre-R5.4 version of this script carry no stamp and cannot be "
    "distinguished from gameplay data, so they are deliberately left in place. up() "
    "never removed Character.faction, so no source data was destroyed either way."
)

CYPHER_DELETE_STAMPED_MEMBER_OF = """
MATCH ()-[r:MEMBER_OF]->()
WHERE r.created_by_migration = $migration_id
DELETE r
RETURN count(r) AS deleted
"""

CYPHER_COUNT_STAMPED_MEMBER_OF = """
MATCH ()-[r:MEMBER_OF]->()
WHERE r.created_by_migration = $migration_id
RETURN count(r) AS stamped
"""


async def down(session, *, dry_run: bool = False) -> None:
    """Delete only the MEMBER_OF edges this migration created.

    Args:
        session: Active Neo4j async session (write access required).
        dry_run: When True, report the count and write nothing.
    """
    from _support import record_run

    if dry_run:
        result = await session.run(CYPHER_COUNT_STAMPED_MEMBER_OF, migration_id=MIGRATION_ID)
        record = await result.single()
        stamped = 0 if record is None else record["stamped"]
        print(f"  [dry-run] would delete {stamped} stamped MEMBER_OF edge(s)")
        return

    result = await session.run(CYPHER_DELETE_STAMPED_MEMBER_OF, migration_id=MIGRATION_ID)
    record = await result.single()
    deleted = 0 if record is None else record["deleted"]
    print(f"  deleted {deleted} stamped MEMBER_OF edge(s)")
    await record_run(
        session,
        migration_id=MIGRATION_ID,
        direction="down",
        reversible=REVERSIBLE,
        notes=IRREVERSIBLE_REASON,
    )


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run_migration(dry_run=dry_run))
