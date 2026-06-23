"""
Module: need_writer
Layer: graph
Purpose: Write operations for Need nodes (Phase 7.3 Social Simulation).
         Creates needs, updates their level (clamped to [0, 100]),
         and links satisfier relationships.
Does NOT: read graph state, call LLMs, or import engine-layer code.
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.need.need_decay_engine
"""

from __future__ import annotations

import uuid

from neo4j import AsyncSession


async def create_need(
    session: AsyncSession,
    *,
    character_id: str,
    kind: str,
    level: int,
    decay_rate: int,
) -> str:
    """Create a Need node and link it to a character via HAS_NEED.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the owning character.
        kind: Need category (hunger / social / rest / recreation).
        level: Initial level in [0, 100].
        decay_rate: Points subtracted per tick.

    Returns:
        The generated need ID.
    """
    need_id = str(uuid.uuid4())
    await session.run(
        """
        MATCH (c:Character {id: $character_id})
        CREATE (n:Need {
            id: $need_id,
            kind: $kind,
            level: $level,
            decay_rate: $decay_rate,
            character_id: $character_id
        })
        CREATE (c)-[:HAS_NEED]->(n)
        """,
        character_id=character_id,
        need_id=need_id,
        kind=kind,
        level=max(0, min(100, level)),
        decay_rate=decay_rate,
    )
    return need_id


async def set_need_level(
    session: AsyncSession,
    *,
    need_id: str,
    level: int,
) -> None:
    """Update the level of a Need node, clamping to [0, 100].

    Args:
        session: Active Neo4j async session.
        need_id: ID of the need to update.
        level: New level (clamped to [0, 100] before write).
    """
    clamped = max(0, min(100, level))
    await session.run(
        "MATCH (n:Need {id: $need_id}) SET n.level = $level",
        need_id=need_id,
        level=clamped,
    )


async def link_satisfier(
    session: AsyncSession,
    *,
    location_id: str,
    need_id: str,
    magnitude: int,
) -> None:
    """Create or update a SATISFIES_NEED relationship from a location to a need.

    Uses MERGE so repeated calls are idempotent — only the magnitude is updated.

    Args:
        session: Active Neo4j async session.
        location_id: ID of the satisfying location.
        need_id: ID of the need being satisfied.
        magnitude: Level points restored per tick at this location.
    """
    await session.run(
        """
        MATCH (loc:Location {id: $location_id})
        MATCH (n:Need {id: $need_id})
        MERGE (loc)-[sat:SATISFIES_NEED]->(n)
        SET sat.magnitude = $magnitude
        """,
        location_id=location_id,
        need_id=need_id,
        magnitude=magnitude,
    )
