"""
Module: group_queries
Layer: graph
Purpose: Cypher query strings and read accessors for Group nodes and membership edges.
Does NOT: execute business logic or validate payloads.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.group.group_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_CREATE_GROUP = """
CREATE (g:Group {
    id:                $group_id,
    name:              $name,
    kind:              $kind,
    cohesion:          $cohesion,
    is_secret:         $is_secret,
    formed_at_tick:    $formed_at_tick,
    dissolved_at_tick: null,
    home_location_id:  $home_location_id
})
RETURN g.id AS group_id
"""

CYPHER_ADD_MEMBER = """
MATCH (c:Character {id: $character_id}), (g:Group {id: $group_id})
MERGE (c)-[e:BELONGS_TO_GROUP]->(g)
SET e.role           = $role,
    e.joined_at_tick = $joined_at_tick,
    e.commitment     = $commitment
"""

CYPHER_REMOVE_MEMBER = """
MATCH (c:Character {id: $character_id})-[e:BELONGS_TO_GROUP]->(g:Group {id: $group_id})
DELETE e
"""

CYPHER_DISSOLVE_GROUP = """
MATCH (g:Group {id: $group_id})
SET g.dissolved_at_tick = $tick
"""

# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_GROUPS_FOR_CHARACTER = """
MATCH (c:Character {id: $character_id})-[e:BELONGS_TO_GROUP]->(g:Group)
WHERE $include_dissolved = true OR g.dissolved_at_tick IS NULL
RETURN g.id AS id,
       g.name AS name,
       g.kind AS kind,
       toInteger(g.cohesion) AS cohesion,
       g.is_secret AS is_secret,
       toInteger(g.formed_at_tick) AS formed_at_tick,
       g.dissolved_at_tick AS dissolved_at_tick,
       g.home_location_id AS home_location_id,
       e.role AS role,
       toInteger(e.joined_at_tick) AS joined_at_tick,
       toInteger(e.commitment) AS commitment
"""

CYPHER_GET_MEMBERS = """
MATCH (c:Character)-[e:BELONGS_TO_GROUP]->(g:Group {id: $group_id})
WHERE g.dissolved_at_tick IS NULL
RETURN c.id AS character_id,
       c.name AS character_name,
       e.role AS role,
       toInteger(e.joined_at_tick) AS joined_at_tick,
       toInteger(e.commitment) AS commitment
"""

CYPHER_GET_SHARED_SECRETS = """
MATCH (g:Group {id: $group_id})-[:GROUP_SHARES_SECRET]->(s:Secret)
RETURN s.id AS secret_id,
       s.content AS content,
       toInteger(s.severity) AS severity
"""

CYPHER_GET_GROUP_GOALS = """
MATCH (g:Group {id: $group_id})-[e:GROUP_PURSUES]->(goal:Goal)
RETURN goal.id AS goal_id,
       goal.description AS description,
       toInteger(e.priority) AS priority
"""

CYPHER_GET_HIGH_AFFECTION_PAIRS = """
MATCH (a:Character {is_active: true})-[r1:RELATES_TO]->(b:Character {is_active: true})
MATCH (b)-[r2:RELATES_TO]->(a)
WHERE r1.affection > $threshold AND r2.affection > $threshold
  AND id(a) < id(b)
RETURN a.id AS char_a_id, b.id AS char_b_id,
       [(a)-[:LOCATED_AT]->(l) | l.id][0] AS loc_a,
       [(b)-[:LOCATED_AT]->(l) | l.id][0] AS loc_b
"""

CYPHER_GET_EXISTING_SHARED_GROUPS = """
MATCH (a:Character {id: $char_a_id})-[:BELONGS_TO_GROUP]->(g:Group {kind: 'clique'})
MATCH (b:Character {id: $char_b_id})-[:BELONGS_TO_GROUP]->(g)
WHERE g.dissolved_at_tick IS NULL
RETURN g.id AS group_id LIMIT 1
"""

CYPHER_GET_STALE_CLIQUES = """
MATCH (g:Group {kind: 'clique'})
WHERE g.dissolved_at_tick IS NULL
  AND g.formed_at_tick < $stale_before_tick
RETURN g.id AS group_id
"""


async def get_groups_for_character(
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
    result = await session.run(
        CYPHER_GET_GROUPS_FOR_CHARACTER,
        character_id=character_id,
        include_dissolved=include_dissolved,
    )
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_members(
    session: AsyncSession,
    *,
    group_id: str,
) -> list[dict[str, Any]]:
    """Fetch active members of a group.

    Args:
        session: Active Neo4j async session.
        group_id: ID of the Group node.

    Returns:
        List of member dicts with role and commitment.
    """
    result = await session.run(CYPHER_GET_MEMBERS, group_id=group_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_shared_secrets(
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
    result = await session.run(CYPHER_GET_SHARED_SECRETS, group_id=group_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_group_goals(
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
    result = await session.run(CYPHER_GET_GROUP_GOALS, group_id=group_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_high_affection_pairs(
    session: AsyncSession,
    *,
    threshold: int,
) -> list[dict[str, Any]]:
    """Fetch co-located character pairs with bidirectional affection above threshold.

    Args:
        session: Active Neo4j async session.
        threshold: Minimum affection value on both RELATES_TO edges.

    Returns:
        List of dicts: char_a_id, char_b_id, loc_a, loc_b.
    """
    result = await session.run(CYPHER_GET_HIGH_AFFECTION_PAIRS, threshold=threshold)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_existing_shared_group(
    session: AsyncSession,
    *,
    char_a_id: str,
    char_b_id: str,
) -> dict[str, Any] | None:
    """Check whether two characters already share an active clique Group.

    Args:
        session: Active Neo4j async session.
        char_a_id: ID of the first character.
        char_b_id: ID of the second character.

    Returns:
        Dict with group_id if a shared active clique exists; None otherwise.
    """
    result = await session.run(
        CYPHER_GET_EXISTING_SHARED_GROUPS,
        char_a_id=char_a_id,
        char_b_id=char_b_id,
    )
    record = await result.single()
    return dict(record) if record is not None else None


async def get_stale_cliques(
    session: AsyncSession,
    *,
    stale_before_tick: int,
) -> list[str]:
    """Fetch IDs of clique Groups formed before the staleness threshold.

    Args:
        session: Active Neo4j async session.
        stale_before_tick: Tick cutoff; cliques formed before this are stale.

    Returns:
        List of group_id strings for stale, undissolved cliques.
    """
    result = await session.run(CYPHER_GET_STALE_CLIQUES, stale_before_tick=stale_before_tick)
    return [r["group_id"] async for r in result]
