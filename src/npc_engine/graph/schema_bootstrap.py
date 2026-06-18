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

# Composite indexes — (name, label, comma-separated property list). DialogueTurn (DEC-106/F3.5)
# is queried/ordered/pruned by (npc_id, player_id, tick) during session save/load.
_COMPOSITE_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("dialogue_turn_pair_tick_index", "DialogueTurn", "n.npc_id, n.player_id, n.tick"),
)

_CYPHER_CREATE_INDEX_TEMPLATE = (
    "CREATE INDEX {name} IF NOT EXISTS FOR (n:{label}) ON ({properties})"
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
    for name, label, properties in _COMPOSITE_INDEXES:
        cypher = _CYPHER_CREATE_INDEX_TEMPLATE.format(name=name, label=label, properties=properties)
        _logger.info("schema_bootstrap: ensuring index name=%s label=%s", name, label)
        await session.run(cypher)
    _logger.info(
        "schema_bootstrap: %d core constraints + %d indexes verified",
        len(_CORE_LABELS), len(_COMPOSITE_INDEXES),
    )
