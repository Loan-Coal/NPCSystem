"""
Module: political_title_writer
Layer: graph
Purpose: Write operations for Title nodes and HOLDS_TITLE / HEIR_OF edges.
Does NOT: call LLMs or implement succession logic.
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.succession.succession_engine
"""

from __future__ import annotations

import uuid

from neo4j import AsyncSession


_CYPHER_CREATE_TITLE = """
CREATE (t:Title {
    id: $id,
    name: $name,
    faction_id: $faction_id,
    power: $power,
    is_inheritable: $is_inheritable
})
"""

_CYPHER_REMOVE_HOLDS_TITLE = """
MATCH (c:Character)-[h:HOLDS_TITLE]->(t:Title {id: $title_id})
DELETE h
"""

_CYPHER_CREATE_HOLDS_TITLE = """
MATCH (c:Character {id: $character_id})
MATCH (t:Title {id: $title_id})
CREATE (c)-[:HOLDS_TITLE {since_tick: $since_tick}]->(t)
"""

_CYPHER_CREATE_HEIR_OF = """
MATCH (heir:Character {id: $heir_id})
MATCH (predecessor:Character {id: $predecessor_id})
MERGE (heir)-[h:HEIR_OF {predecessor_id: $predecessor_id}]->(predecessor)
SET h.priority = $priority, h.legitimacy = $legitimacy
"""


async def create_title(
    session: AsyncSession,
    *,
    name: str,
    faction_id: str,
    power: int,
    is_inheritable: bool,
) -> str:
    """Create a Title node and return its ID.

    Args:
        session: Active Neo4j async session.
        name: Title name (e.g., 'Duke of Ember').
        faction_id: ID of the Faction that owns this title.
        power: Political power value of the title.
        is_inheritable: Whether the title passes to heirs on vacancy.

    Returns:
        ID of the newly created Title node.
    """
    title_id = str(uuid.uuid4())
    await session.run(
        _CYPHER_CREATE_TITLE,
        id=title_id,
        name=name,
        faction_id=faction_id,
        power=power,
        is_inheritable=is_inheritable,
    )
    return title_id


async def grant_title(
    session: AsyncSession,
    *,
    character_id: str,
    title_id: str,
    tick: int,
) -> None:
    """Grant a title to a character, removing any existing holder first.

    This removes all existing HOLDS_TITLE edges for the title before creating
    the new one, ensuring exactly one holder at a time.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character receiving the title.
        title_id: ID of the Title node.
        tick: Current game tick (stored on the HOLDS_TITLE edge as since_tick).
    """
    await session.run(_CYPHER_REMOVE_HOLDS_TITLE, title_id=title_id)
    await session.run(
        _CYPHER_CREATE_HOLDS_TITLE,
        character_id=character_id,
        title_id=title_id,
        since_tick=tick,
    )


async def add_heir(
    session: AsyncSession,
    *,
    heir_id: str,
    predecessor_id: str,
    priority: int,
    legitimacy: int,
) -> None:
    """Register a character as heir to another character.

    Uses MERGE so re-registering an heir updates priority/legitimacy without duplicating.

    Args:
        session: Active Neo4j async session.
        heir_id: ID of the heir Character node.
        predecessor_id: ID of the predecessor Character node.
        priority: Succession order — lower number means higher priority.
        legitimacy: Legitimacy score 0–100.
    """
    await session.run(
        _CYPHER_CREATE_HEIR_OF,
        heir_id=heir_id,
        predecessor_id=predecessor_id,
        priority=priority,
        legitimacy=legitimacy,
    )
