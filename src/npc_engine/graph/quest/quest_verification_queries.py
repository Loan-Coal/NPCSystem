"""
Module: quest_verification_queries
Layer: graph
Purpose: Cypher queries for verifying quest objective completion states.
Does NOT: validate business logic or call LLMs.
Dependencies injected: AsyncSession (caller-managed).
Used by: engines.interaction.quest_verifier
"""
from __future__ import annotations

from neo4j import AsyncSession

_CYPHER_PLAYER_HAS_ITEM = """
MATCH (p:Character {id: $player_id})-[:OWNS]->(i:Item {id: $item_id})
RETURN count(i) AS cnt
"""

_CYPHER_PLAYER_LOCATED_AT = """
MATCH (p:Character {id: $player_id})-[:LOCATED_AT]->(l:Location {id: $location_id})
RETURN count(l) AS cnt
"""

_CYPHER_PLAYER_WAS_AT = """
MATCH (p:Character {id: $player_id})-[:WAS_AT]->(l:Location {id: $location_id})
RETURN count(l) AS cnt
"""

_CYPHER_TARGET_INACTIVE = """
MATCH (c:Character {id: $target_id})
WHERE c.is_active = false
RETURN count(c) AS cnt
"""

_CYPHER_PLAYER_CO_LOCATED_WITH = """
MATCH (p:Character {id: $player_id})-[:LOCATED_AT]->(loc:Location)<-[:LOCATED_AT]-(t:Character {id: $target_id})
RETURN count(loc) AS cnt
"""


async def count_player_has_item(session: AsyncSession, player_id: str, item_id: str) -> int:
    """Return count of OWNS edges from player to item (0 or ≥1).

    Args:
        session: Active Neo4j async session.
        player_id: Character node ID of the player.
        item_id: Item node ID to check ownership of.

    Returns:
        Count of matching OWNS edges.
    """
    result = await session.run(_CYPHER_PLAYER_HAS_ITEM, player_id=player_id, item_id=item_id)
    record = await result.single()
    return int(record["cnt"]) if record is not None else 0


async def count_player_located_at(session: AsyncSession, player_id: str, location_id: str) -> int:
    """Return count of current LOCATED_AT edges from player to location.

    Args:
        session: Active Neo4j async session.
        player_id: Character node ID of the player.
        location_id: Location node ID to check current presence at.

    Returns:
        Count of matching LOCATED_AT edges.
    """
    result = await session.run(_CYPHER_PLAYER_LOCATED_AT, player_id=player_id, location_id=location_id)
    record = await result.single()
    return int(record["cnt"]) if record is not None else 0


async def count_player_was_at(session: AsyncSession, player_id: str, location_id: str) -> int:
    """Return count of historical WAS_AT edges from player to location.

    Args:
        session: Active Neo4j async session.
        player_id: Character node ID of the player.
        location_id: Location node ID to check historical presence at.

    Returns:
        Count of matching WAS_AT edges.
    """
    result = await session.run(_CYPHER_PLAYER_WAS_AT, player_id=player_id, location_id=location_id)
    record = await result.single()
    return int(record["cnt"]) if record is not None else 0


async def count_target_inactive(session: AsyncSession, target_id: str) -> int:
    """Return count of Character nodes with given id where is_active=False.

    Args:
        session: Active Neo4j async session.
        target_id: Character node ID of the kill target.

    Returns:
        1 if the target exists and is inactive, 0 otherwise.
    """
    result = await session.run(_CYPHER_TARGET_INACTIVE, target_id=target_id)
    record = await result.single()
    return int(record["cnt"]) if record is not None else 0


async def count_player_co_located_with(session: AsyncSession, player_id: str, target_id: str) -> int:
    """Return count of shared Location nodes where player and target are both LOCATED_AT.

    Args:
        session: Active Neo4j async session.
        player_id: Character node ID of the player.
        target_id: Character node ID of the NPC to co-locate with.

    Returns:
        Count of shared Location nodes (0 or ≥1).
    """
    result = await session.run(_CYPHER_PLAYER_CO_LOCATED_WITH, player_id=player_id, target_id=target_id)
    record = await result.single()
    return int(record["cnt"]) if record is not None else 0
