#!/usr/bin/env python
"""
Module: _support (scripts.migrations)
Layer: scripts (dev tooling)
Purpose: Shared plumbing for the migration scripts — credential resolution, the
         applied-state ledger write, and a down() helper for dropping constraints.
Does NOT: decide migration order, discover migrations, or run them unattended.
Dependencies: datetime, os, sys, pathlib, neo4j, npc_engine.graph.infra
Dependencies injected: NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD from the environment.
Used by: every module in scripts/migrations/

Underscore-prefixed so scripts/check_migrations.py's *.py glob and the R5.4 contract
test both skip it — it is plumbing, not a migration.

Credentials come from the environment with NO hardcoded password default. Two of the six
migrations previously defaulted --password to "password", which is a shipped credential
in a script that writes to a customer's graph (CR-L16-09's problem, in a second place).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(_SRC_ROOT) not in sys.path[:1]:
    sys.path.insert(0, str(_SRC_ROOT))

from neo4j import AsyncSession  # noqa: E402

from npc_engine.graph.infra.migration_state_models import (  # noqa: E402
    MigrationDirection,
    MigrationRecord,
    Reversibility,
)
from npc_engine.graph.infra.migration_state_writer import (  # noqa: E402
    ensure_ledger_constraint,
    record_migration,
)

DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"

_CYPHER_DROP_CONSTRAINT = "DROP CONSTRAINT {name} IF EXISTS"


class MissingCredentialError(RuntimeError):
    """Raised when NEO4J_PASSWORD is not set and no --password was given."""


def resolve_credentials(password: str | None = None) -> tuple[str, str, str]:
    """Return (uri, user, password), preferring an explicit argument over the environment.

    Args:
        password: Password supplied on the command line, if any.

    Returns:
        The connection triple.

    Raises:
        MissingCredentialError: When no password is available from either source.
    """
    resolved = password or os.environ.get("NEO4J_PASSWORD")
    if not resolved:
        raise MissingCredentialError(
            "NEO4J_PASSWORD is not set. Pass --password or export NEO4J_PASSWORD; "
            "these scripts ship no default credential."
        )
    return (
        os.environ.get("NEO4J_URI", DEFAULT_URI),
        os.environ.get("NEO4J_USER", DEFAULT_USER),
        resolved,
    )


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


async def record_run(
    session: AsyncSession,
    *,
    migration_id: str,
    direction: MigrationDirection,
    reversible: Reversibility,
    notes: str = "",
) -> None:
    """Record that a migration ran, creating the ledger constraint first if needed.

    Args:
        session: Active Neo4j async session (write access required).
        migration_id: The migration's MIGRATION_ID.
        direction: "up" or "down".
        reversible: The migration's declared REVERSIBLE value.
        notes: Optional free text, e.g. what a partial down could not restore.
    """
    await ensure_ledger_constraint(session)
    await record_migration(
        session,
        MigrationRecord(
            id=migration_id,
            direction=direction,
            applied_at_iso=utc_now_iso(),
            reversible=reversible,
            notes=notes,
        ),
    )


async def drop_constraints(session: AsyncSession, names: tuple[str, ...], *, dry_run: bool = False) -> None:
    """Drop named constraints if they exist; idempotent and data-preserving.

    Dropping a uniqueness constraint removes an invariant, never a node or a property,
    which is why every constraint-only migration here is fully reversible.

    Args:
        session: Active Neo4j async session (write access required).
        names: Constraint names to drop.
        dry_run: When True, print the plan and write nothing.
    """
    for name in names:
        statement = _CYPHER_DROP_CONSTRAINT.format(name=name)
        if dry_run:
            print(f"  [dry-run] {statement}")
            continue
        await session.run(statement)
        print(f"  dropped constraint {name}")
