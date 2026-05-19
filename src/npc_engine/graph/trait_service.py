"""
Module: trait_service
Layer: graph
Purpose: Create, read, and remove character trait relationships via HAS_TRAIT edges.
Does NOT: implement business logic or call LLMs.
Dependencies: graph.trait_queries
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.traits, npc_engine.retrieval.subgraph_retriever
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.trait_queries import (
    CYPHER_DELETE_HAS_TRAIT,
    CYPHER_MERGE_HAS_TRAIT,
    get_traits,
)


async def add_trait(
    session: AsyncSession,
    *,
    character_id: str,
    trait_id: str,
    intensity: int,
    is_secret: bool = False,
) -> None:
    """Create or update a HAS_TRAIT edge between a character and a trait.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.
        trait_id: ID of the Trait node.
        intensity: How strongly the character exhibits this trait (0–100).
        is_secret: Whether this trait is hidden from other characters.
    """
    await session.run(
        CYPHER_MERGE_HAS_TRAIT,
        character_id=character_id,
        trait_id=trait_id,
        intensity=intensity,
        is_secret=is_secret,
    )


async def get_traits_svc(
    session: AsyncSession,
    character_id: str,
) -> list[dict[str, Any]]:
    """Return all traits for a character ordered by intensity descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.

    Returns:
        List of trait dicts.
    """
    return await get_traits(session, character_id=character_id)


async def remove_trait(
    session: AsyncSession,
    *,
    character_id: str,
    trait_id: str,
) -> None:
    """Remove a HAS_TRAIT edge between a character and a trait.

    No-op if the edge does not exist.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.
        trait_id: ID of the Trait node.
    """
    await session.run(
        CYPHER_DELETE_HAS_TRAIT,
        character_id=character_id,
        trait_id=trait_id,
    )
