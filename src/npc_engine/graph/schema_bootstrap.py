"""
Module: schema_bootstrap
Layer: graph
Purpose: Ensure core-node uniqueness constraints exist in Neo4j at startup.
Does NOT: execute domain queries, write graph data, or call any engine.
Dependencies injected: neo4j.AsyncSession (caller-provided)
Used by: npc_engine.main (lifespan bootstrap)
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — one entry per core node label.
# Constraint name mirrors the pattern: <lowercase_label>_id_unique
# ---------------------------------------------------------------------------

_CORE_LABELS: tuple[tuple[str, str], ...] = (
    ("Character",   "character_id_unique"),
    ("Event",       "event_id_unique"),
    ("Location",    "location_id_unique"),
    ("WorldState",  "world_state_id_unique"),
    ("Item",        "item_id_unique"),
    ("Quest",       "quest_id_unique"),
    ("Faction",     "faction_id_unique"),
)

_CYPHER_CREATE_CONSTRAINT_TEMPLATE = (
    "CREATE CONSTRAINT {name} IF NOT EXISTS "
    "FOR (n:{label}) REQUIRE n.id IS UNIQUE"
)


async def ensure_core_constraints(session: AsyncSession) -> None:
    """Create uniqueness constraints for all core node labels if they do not exist.

    Issues one ``CREATE CONSTRAINT … IF NOT EXISTS`` statement per label so the
    operation is fully idempotent — safe to call on every process startup.

    Args:
        session: Active Neo4j async session (write access required).

    Raises:
        Exception: Re-raises any Neo4j driver error encountered while issuing
            the constraint statements so the caller can decide whether startup
            should abort.
    """
    for label, name in _CORE_LABELS:
        cypher = _CYPHER_CREATE_CONSTRAINT_TEMPLATE.format(name=name, label=label)
        _logger.info(
            "schema_bootstrap: ensuring constraint name=%s label=%s",
            name,
            label,
        )
        await session.run(cypher)
    _logger.info(
        "schema_bootstrap: all %d core constraints verified", len(_CORE_LABELS)
    )
