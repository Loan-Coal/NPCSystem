"""
Module: quest_generation_queries
Layer: graph
Purpose: Cypher read queries for quest generation — character info,
         candidate node IDs, node label validation, and template skill requirements.
Does NOT: write to the graph, open transactions, or call LLMs.
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.quest_generation.quest_generation_engine,
         npc_engine.engines.quest_generation.slot_validator
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.generic.generic_graph_utils import cypher_identifier

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_GET_CHARACTER = (
    "MATCH (c:Character {id: $character_id}) "
    "RETURN c.archetype AS archetype, c.name AS name"
)

CYPHER_CHECK_NODE = (
    "MATCH (n {id: $node_id}) RETURN labels(n) AS labels LIMIT 1"
)

CYPHER_TEMPLATE_SKILL_REQS = """
MATCH (qt:QuestTemplate {id: $template_id})-[r:REQUIRES_SKILL]->(s:Skill)
RETURN s.id AS skill_id, toInteger(r.min_level) AS min_level
"""

_CANDIDATE_LIMIT = 20


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_character_info(
    session: AsyncSession,
    character_id: str,
) -> tuple[str, str]:
    """Fetch archetype and name for a character node.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.

    Returns:
        Tuple of (archetype, name); defaults to ("default", character_id) when
        the node is missing or fields are absent.

    Raises:
        ValueError: If the Character node is not found in the graph.
    """
    result = await session.run(CYPHER_GET_CHARACTER, character_id=character_id)
    records = [dict(r) async for r in result]
    if not records:
        raise ValueError(f"Character '{character_id}' not found in graph")
    row = records[0]
    return str(row.get("archetype") or "default"), str(row.get("name") or character_id)


async def get_candidate_ids_by_label(
    session: AsyncSession,
    label: str,
    limit: int = _CANDIDATE_LIMIT,
) -> list[str]:
    """Return up to `limit` node IDs matching the given node label.

    The label is sanitised via cypher_identifier before interpolation so that
    dynamic labels cannot inject arbitrary Cypher.

    Args:
        session: Active Neo4j async session.
        label: Node label to query (e.g. "Character", "Item").
        limit: Maximum number of IDs to return (default 20).

    Returns:
        List of node ID strings; empty list if no nodes of that label exist.
    """
    safe_label = cypher_identifier(label)
    cypher = f"MATCH (n:{safe_label}) RETURN n.id AS id LIMIT {int(limit)}"
    result = await session.run(cypher)
    return [str(r["id"]) async for r in result if r.get("id") is not None]


async def check_node_labels(
    session: AsyncSession,
    node_id: str,
) -> list[str] | None:
    """Return the labels for a node ID, or None if the node does not exist.

    Args:
        session: Active Neo4j async session.
        node_id: ID of the node to look up.

    Returns:
        List of label strings, or None if no node with that ID was found.
    """
    result = await session.run(CYPHER_CHECK_NODE, node_id=node_id)
    records = [dict(r) async for r in result]
    if not records:
        return None
    return list(records[0].get("labels", []))


async def get_template_skill_requirements(
    session: AsyncSession,
    template_id: str,
) -> list[dict[str, Any]]:
    """Fetch REQUIRES_SKILL constraints from a QuestTemplate node.

    Args:
        session: Active Neo4j async session.
        template_id: ID of the QuestTemplate node.

    Returns:
        List of dicts with keys skill_id (str) and min_level (int); empty if none.
    """
    result = await session.run(CYPHER_TEMPLATE_SKILL_REQS, template_id=template_id)
    return [dict(r) async for r in result]
