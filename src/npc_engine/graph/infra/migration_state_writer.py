"""
Module: migration_state_writer
Layer: graph
Purpose: Record that a schema migration ran, so re-running one is a detectable no-op
         rather than a silent re-application against a customer's data.
Does NOT: run migrations, decide ordering, or read the ledger back.
Dependencies injected: neo4j.AsyncSession (caller-provided)
Used by: scripts/migrations/_support.py

Cypher for the ledger lives here rather than in scripts/ because graph/ is the only
layer allowed to run it. The six migration scripts still hold their own inline Cypher —
pre-existing debt logged as ISSUE-268, deliberately not widened by this module.
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession

from npc_engine.graph.infra.migration_state_models import (
    SCHEMA_MIGRATION_LABEL,
    MigrationRecord,
)

_logger = logging.getLogger(__name__)

# The ledger's own uniqueness constraint. Created here rather than by a migration,
# because a migration cannot be the thing that creates the migration ledger.
CYPHER_ENSURE_LEDGER_CONSTRAINT = (
    f"CREATE CONSTRAINT schema_migration_id_unique IF NOT EXISTS "
    f"FOR (m:{SCHEMA_MIGRATION_LABEL}) REQUIRE m.id IS UNIQUE"
)

CYPHER_RECORD_MIGRATION = f"""
MERGE (m:{SCHEMA_MIGRATION_LABEL} {{id: $id}})
SET m.direction = $direction,
    m.applied_at = $applied_at_iso,
    m.reversible = $reversible,
    m.notes = $notes
RETURN m.id AS id
"""

CYPHER_READ_APPLIED = f"""
MATCH (m:{SCHEMA_MIGRATION_LABEL} {{id: $id}})
RETURN m.direction AS direction
"""


async def ensure_ledger_constraint(session: AsyncSession) -> None:
    """Create the ledger's uniqueness constraint if it does not exist.

    Args:
        session: Active Neo4j async session (write access required).
    """
    await session.run(CYPHER_ENSURE_LEDGER_CONSTRAINT)


async def record_migration(session: AsyncSession, record: MigrationRecord) -> None:
    """Write one applied-state entry, replacing any previous entry for that id.

    Args:
        session: Active Neo4j async session (write access required).
        record: The migration run to record.
    """
    await session.run(CYPHER_RECORD_MIGRATION, **record.model_dump())
    _logger.info(
        "migration_recorded",
        extra={"migration_id": record.id, "direction": record.direction},
    )


async def applied_direction(session: AsyncSession, migration_id: str) -> str | None:
    """Return the last recorded direction for a migration, or None if never recorded.

    Args:
        session: Active Neo4j async session.
        migration_id: Migration module stem.

    Returns:
        "up", "down", or None when the ledger holds no entry for this migration.
    """
    result = await session.run(CYPHER_READ_APPLIED, id=migration_id)
    record = await result.single()
    return None if record is None else str(record["direction"])
