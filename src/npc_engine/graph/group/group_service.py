"""
Module: group_service
Layer: graph
Purpose: Functions for creating and managing Group nodes and membership edges.
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies: graph.group_queries
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.clique.clique_formation_engine, npc_engine.api.routes.groups
"""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.group.group_queries import (
    CYPHER_ADD_MEMBER,
    CYPHER_CREATE_GROUP,
    CYPHER_DISSOLVE_GROUP,
    CYPHER_REMOVE_MEMBER,
    get_group_goals,
    get_groups_for_character,
    get_members,
    get_shared_secrets,
)


async def create_group(
    session: AsyncSession,
    *,
    name: str,
    kind: str,
    cohesion: int,
    is_secret: bool,
    formed_at_tick: int,
    home_location_id: str | None = None,
) -> str:
    """Create a new Group node and return its ID.

    Args:
        session: Active Neo4j async session.
        name: Human-readable group name.
        kind: Group type (clique, conspiracy, family, crew, fellowship, mob).
        cohesion: Initial cohesion score (0–100).
        is_secret: Whether the group's existence is hidden.
        formed_at_tick: Game tick at which the group formed.
        home_location_id: Optional location node ID for the group's home base.

    Returns:
        Generated UUID string for the new Group node.
    """
    group_id = str(uuid.uuid4())
    await session.run(
        CYPHER_CREATE_GROUP,
        group_id=group_id,
        name=name,
        kind=kind,
        cohesion=cohesion,
        is_secret=is_secret,
        formed_at_tick=formed_at_tick,
        home_location_id=home_location_id,
    )
    return group_id


async def add_member(
    session: AsyncSession,
    *,
    group_id: str,
    character_id: str,
    role: str,
    joined_at_tick: int,
    commitment: int,
) -> None:
    """Add or update a character's membership in a group via BELONGS_TO_GROUP edge.

    Args:
        session: Active Neo4j async session.
        group_id: ID of the Group node.
        character_id: ID of the Character node.
        role: The character's role within the group.
        joined_at_tick: Game tick when the character joined.
        commitment: How committed the character is (0–100).
    """
    await session.run(
        CYPHER_ADD_MEMBER,
        character_id=character_id,
        group_id=group_id,
        role=role,
        joined_at_tick=joined_at_tick,
        commitment=commitment,
    )


async def remove_member(
    session: AsyncSession,
    *,
    group_id: str,
    character_id: str,
) -> None:
    """Remove a character's membership edge from a group.

    Args:
        session: Active Neo4j async session.
        group_id: ID of the Group node.
        character_id: ID of the Character node.
    """
    await session.run(
        CYPHER_REMOVE_MEMBER,
        character_id=character_id,
        group_id=group_id,
    )


async def get_groups_for_character_svc(
    session: AsyncSession,
    *,
    character_id: str,
    include_dissolved: bool = False,
) -> list[dict[str, Any]]:
    """Fetch groups a character belongs to.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        include_dissolved: When True, also returns dissolved groups.

    Returns:
        List of group membership dicts.
    """
    return await get_groups_for_character(
        session, character_id=character_id, include_dissolved=include_dissolved
    )


async def get_members_svc(
    session: AsyncSession,
    *,
    group_id: str,
) -> list[dict[str, Any]]:
    """Fetch active members of a group.

    Args:
        session: Active Neo4j async session.
        group_id: ID of the Group node.

    Returns:
        List of member dicts.
    """
    return await get_members(session, group_id=group_id)


async def dissolve_group(
    session: AsyncSession,
    *,
    group_id: str,
    tick: int,
) -> None:
    """Mark a group as dissolved at the given tick.

    Args:
        session: Active Neo4j async session.
        group_id: ID of the Group node.
        tick: Game tick at which the group dissolved.
    """
    await session.run(CYPHER_DISSOLVE_GROUP, group_id=group_id, tick=tick)


async def get_shared_secrets_svc(
    session: AsyncSession,
    *,
    group_id: str,
) -> list[dict[str, Any]]:
    """Fetch secrets shared within a group.

    Args:
        session: Active Neo4j async session.
        group_id: ID of the Group node.

    Returns:
        List of secret dicts.
    """
    return await get_shared_secrets(session, group_id=group_id)


async def get_group_goals_svc(
    session: AsyncSession,
    *,
    group_id: str,
) -> list[dict[str, Any]]:
    """Fetch goals pursued by a group.

    Args:
        session: Active Neo4j async session.
        group_id: ID of the Group node.

    Returns:
        List of goal dicts with priority.
    """
    return await get_group_goals(session, group_id=group_id)
