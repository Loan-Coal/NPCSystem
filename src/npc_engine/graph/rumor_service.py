"""
Module: rumor_service
Layer: graph
Purpose: Functions for creating and querying Rumor nodes and BELIEVES_RUMOR edges.
Does NOT: implement business logic or call LLMs.
Dependencies: graph.rumor_queries
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.gossip.gossip_handler, npc_engine.api.routes.rumors,
         npc_engine.retrieval.context.context_builder
"""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.rumor_queries import (
    CYPHER_BELIEVE_RUMOR,
    CYPHER_CREATE_DERIVED_RUMOR,
    CYPHER_MERGE_ROOT_RUMOR,
    get_rumor_believers,
    get_rumor_tree,
    get_rumors_about_event,
    get_rumors_for_character,
)


def _root_rumor_id(origin_event_id: str) -> str:
    """Compute a deterministic rumor ID for the root rumor of an event."""
    return f"rumor:root:{origin_event_id}"


async def create_rumor(
    session: AsyncSession,
    *,
    content: str,
    origin_event_id: str | None = None,
    created_at_tick: int,
    mutation_distance: int = 0,
    severity: int,
    is_fabricated: bool = False,
) -> str:
    """Merge (or create) a root Rumor node and return its ID.

    Root rumors are keyed by ``origin_event_id`` — calling this for the same event
    multiple times is idempotent; the first propagation creates the node, subsequent
    calls return the existing ID.

    Args:
        session: Active Neo4j async session.
        content: Rumor text content.
        origin_event_id: ID of the originating Event node, or None for fabricated rumors.
        created_at_tick: Game tick at which the rumor was created.
        mutation_distance: Distortion depth from the original event (0 = root).
        severity: Severity copied from the originating event (0–100).
        is_fabricated: True when the rumor was invented, not derived from a real event.

    Returns:
        Rumor node ID string.
    """
    rumor_id = _root_rumor_id(origin_event_id) if origin_event_id else str(uuid.uuid4())
    await session.run(
        CYPHER_MERGE_ROOT_RUMOR,
        rumor_id=rumor_id,
        content=content,
        origin_event_id=origin_event_id,
        created_at_tick=created_at_tick,
        severity=severity,
        is_fabricated=is_fabricated,
    )
    return rumor_id


async def create_derived_rumor(
    session: AsyncSession,
    *,
    parent_rumor_id: str,
    content: str,
    mutation_type: str,
    created_at_tick: int,
) -> str:
    """Create a derived Rumor node linked by DERIVED_FROM to its parent.

    Args:
        session: Active Neo4j async session.
        parent_rumor_id: ID of the parent Rumor node.
        content: Derived rumor text content.
        mutation_type: Type of distortion applied (omission, exaggeration, etc.).
        created_at_tick: Game tick at which the derived rumor was created.

    Returns:
        New Rumor node ID string.
    """
    rumor_id = str(uuid.uuid4())
    await session.run(
        CYPHER_CREATE_DERIVED_RUMOR,
        rumor_id=rumor_id,
        parent_rumor_id=parent_rumor_id,
        content=content,
        mutation_type=mutation_type,
        created_at_tick=created_at_tick,
    )
    return rumor_id


async def believe_rumor(
    session: AsyncSession,
    *,
    character_id: str,
    rumor_id: str,
    confidence: int,
    tick: int,
    from_character_id: str | None = None,
) -> None:
    """Create or update a BELIEVES_RUMOR edge from a character to a rumor.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character who believes the rumor.
        rumor_id: ID of the Rumor node.
        confidence: Belief confidence (0–100).
        tick: Game tick at which the belief was recorded.
        from_character_id: Optional ID of the character who spread the rumor.
    """
    await session.run(
        CYPHER_BELIEVE_RUMOR,
        character_id=character_id,
        rumor_id=rumor_id,
        confidence=confidence,
        tick=tick,
        from_character_id=from_character_id,
    )


async def get_rumors_for_character_svc(
    session: AsyncSession,
    *,
    character_id: str,
    min_confidence: int = 0,
) -> list[dict[str, Any]]:
    """Fetch rumors a character believes.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        min_confidence: Minimum confidence level to include.

    Returns:
        List of rumor belief dicts ordered by confidence descending.
    """
    return await get_rumors_for_character(
        session, character_id=character_id, min_confidence=min_confidence
    )


async def get_rumor_tree_svc(
    session: AsyncSession,
    *,
    rumor_id: str,
) -> list[dict[str, Any]]:
    """Fetch the derivation tree of a rumor.

    Args:
        session: Active Neo4j async session.
        rumor_id: ID of the root Rumor node.

    Returns:
        List of derived rumor dicts ordered by depth.
    """
    return await get_rumor_tree(session, rumor_id=rumor_id)


async def get_rumor_believers_svc(
    session: AsyncSession,
    *,
    rumor_id: str,
) -> list[dict[str, Any]]:
    """Fetch characters who believe a rumor.

    Args:
        session: Active Neo4j async session.
        rumor_id: ID of the Rumor node.

    Returns:
        List of believer dicts.
    """
    return await get_rumor_believers(session, rumor_id=rumor_id)


async def get_rumors_about_event_svc(
    session: AsyncSession,
    *,
    event_id: str,
) -> list[dict[str, Any]]:
    """Fetch rumors originating from a specific event.

    Args:
        session: Active Neo4j async session.
        event_id: ID of the originating Event node.

    Returns:
        List of rumor dicts.
    """
    return await get_rumors_about_event(session, event_id=event_id)
