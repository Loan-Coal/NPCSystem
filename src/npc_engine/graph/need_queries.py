"""
Module: need_queries
Layer: graph
Purpose: Read-only Cypher queries for Need nodes (Phase 7.3 Social Simulation).
         Returns dicts suitable for engine processing.
Does NOT: write to the graph, call LLMs, or import engine-layer code.
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.need.need_decay_engine
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession


async def get_needs_for_character(
    session: AsyncSession,
    character_id: str,
) -> list[dict[str, Any]]:
    """Fetch all Need nodes owned by a character.

    Args:
        session: Active Neo4j async session.
        character_id: The character whose needs to retrieve.

    Returns:
        List of dicts with keys: need_id, kind, level, decay_rate, character_id.
    """
    result = await session.run(
        """
        MATCH (c:Character {id: $character_id})-[:HAS_NEED]->(n:Need)
        RETURN n.id AS need_id,
               n.kind AS kind,
               n.level AS level,
               n.decay_rate AS decay_rate,
               $character_id AS character_id
        """,
        character_id=character_id,
    )
    return [dict(r) async for r in result]


async def get_all_needs_below_threshold(
    session: AsyncSession,
    *,
    threshold: int,
) -> list[dict[str, Any]]:
    """Fetch all Need nodes whose level is at or below threshold.

    Args:
        session: Active Neo4j async session.
        threshold: Maximum level to include (inclusive).

    Returns:
        List of dicts with keys: need_id, kind, level, decay_rate, character_id.
    """
    result = await session.run(
        """
        MATCH (c:Character)-[:HAS_NEED]->(n:Need)
        WHERE n.level <= $threshold
        RETURN n.id AS need_id,
               n.kind AS kind,
               n.level AS level,
               n.decay_rate AS decay_rate,
               c.id AS character_id
        """,
        threshold=threshold,
    )
    return [dict(r) async for r in result]


async def get_all_needs_with_location(
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """Fetch all Need nodes joined with the character's current location and any satisfiers.

    This is the primary query for NeedDecayEngine — one round-trip to compute
    net decay for all characters simultaneously.

    The query uses OPTIONAL MATCH for satisfiers so that needs without a satisfier
    at the character's location still appear in the result.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of dicts with keys:
            need_id, kind, level, decay_rate, character_id,
            location_id (nullable), satisfaction_magnitude (0 if no satisfier).
    """
    result = await session.run(
        """
        MATCH (c:Character)-[:HAS_NEED]->(n:Need)
        OPTIONAL MATCH (c)-[:LOCATED_AT]->(loc:Location)
        OPTIONAL MATCH (loc)-[sat:SATISFIES_NEED]->(n)
        RETURN n.id AS need_id,
               n.kind AS kind,
               n.level AS level,
               n.decay_rate AS decay_rate,
               c.id AS character_id,
               loc.id AS location_id,
               coalesce(sat.magnitude, 0) AS satisfaction_magnitude
        """
    )
    return [dict(r) async for r in result]


async def get_satisfiers_at_location(
    session: AsyncSession,
    *,
    location_id: str,
    need_kind: str,
) -> list[dict[str, Any]]:
    """Fetch SATISFIES_NEED relationships from a location for a specific need kind.

    Args:
        session: Active Neo4j async session.
        location_id: ID of the location to inspect.
        need_kind: The kind of need to match (e.g. 'hunger').

    Returns:
        List of dicts with keys: need_id, magnitude.
    """
    result = await session.run(
        """
        MATCH (loc:Location {id: $location_id})-[sat:SATISFIES_NEED]->(n:Need)
        WHERE n.kind = $need_kind
        RETURN n.id AS need_id, sat.magnitude AS magnitude
        """,
        location_id=location_id,
        need_kind=need_kind,
    )
    return [dict(r) async for r in result]
