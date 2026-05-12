"""
Module: pair_selector
Layer: engines/gossip
Purpose: Selects gossip-eligible NPC pairs with faction-weighted deterministic ordering.
Does NOT: mutate knowledge edges.
Dependencies injected: AsyncSession, GossipWeightConfig.
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.engines.gossip.gossip_config import GossipWeightConfig
from npc_engine.engines.gossip.pair_weighting import compute_faction_weight
from npc_engine.graph.goal_queries import get_goals_for_character


CYPHER_GOSSIP_PAIRS = """
MATCH (a:Character)-[:LOCATED_AT]->(loc:Location)<-[:LOCATED_AT]-(b:Character)
WHERE a.id <> b.id
    AND a.is_player = false AND b.is_player = false
    AND a.is_active = true AND b.is_active = true
OPTIONAL MATCH (a)-[:MEMBER_OF]->(fa:Faction)
WHERE fa.is_active = true
OPTIONAL MATCH (b)-[:MEMBER_OF]->(fb:Faction)
WHERE fb.is_active = true
OPTIONAL MATCH (fa)-[sw:STANDS_WITH]->(fb)
WITH a, b, loc,
     collect(DISTINCT fa.id) AS a_faction_ids,
     collect(DISTINCT fb.id) AS b_faction_ids,
     max(sw.standing) AS best_standing
RETURN properties(a) AS a, properties(b) AS b, properties(loc) AS loc,
       a_faction_ids, b_faction_ids, best_standing
"""

CYPHER_KNOWN_NODE_IDS = """
MATCH (c:Character {id: $character_id})-[:KNOWS_ABOUT]->(n)
RETURN n.id AS node_id
"""

_GOAL_ALIGNMENT_BONUS = 10


def _pair_weight(character: dict) -> int:
    return int(character.get("gossipy", 50))


async def _fetch_goal_target_ids(session: AsyncSession, character_id: str) -> set[str]:
    """Return the set of non-empty target_id values from this character's active goals.

    Args:
        session: Active Neo4j async session.
        character_id: Character node ID to query goals for.

    Returns:
        Set of target_id strings (empty strings excluded).
    """
    goals = await get_goals_for_character(
        session, character_id=character_id, k=20, status_filter="active"
    )
    return {g["target_id"] for g in goals if g.get("target_id")}


async def _fetch_known_node_ids(session: AsyncSession, character_id: str) -> set[str]:
    """Return the set of node IDs this character knows about via KNOWS_ABOUT edges.

    Args:
        session: Active Neo4j async session.
        character_id: Character node ID to query knowledge for.

    Returns:
        Set of known node ID strings.
    """
    result = await session.run(CYPHER_KNOWN_NODE_IDS, character_id=character_id)
    return {record["node_id"] async for record in result if record["node_id"]}


async def select_pairs(
    session: AsyncSession,
    max_pairs: int,
    weight_config: GossipWeightConfig,
) -> list[tuple[dict, dict, dict, dict]]:
    """Return top-weighted directed gossip pairs sorted deterministically.

    Pairs are all co-located active non-player NPC combinations. Ranking uses
    the sum of both characters' ``gossipy`` attributes multiplied by the faction
    weight as the primary key, with an optional +10 goal-alignment bonus when
    either NPC has an active goal whose ``target_id`` matches a node known to
    the other NPC. Character IDs serve as tiebreakers.

    Args:
        session: Active Neo4j async session.
        max_pairs: Maximum number of pairs to return.
        weight_config: Faction weight multipliers for pair ranking.

    Returns:
        List of (sharer, receiver, location, faction_ctx) tuples, limited to max_pairs.
        faction_ctx contains ``a_faction_ids``, ``b_faction_ids``, and ``best_standing``.
    """
    result = await session.run(CYPHER_GOSSIP_PAIRS)
    rows = [record.data() async for record in result]

    # Build goal-alignment bonus map — skip entirely when no rows
    goal_alignment: dict[tuple[str, str], int] = {}
    if rows:
        unique_ids: set[str] = set()
        for row in rows:
            unique_ids.add(row["a"]["id"])
            unique_ids.add(row["b"]["id"])

        goal_targets: dict[str, set[str]] = {}
        known_nodes: dict[str, set[str]] = {}
        any_goals = False
        for npc_id in unique_ids:
            targets = await _fetch_goal_target_ids(session, npc_id)
            goal_targets[npc_id] = targets
            if targets:
                any_goals = True

        if any_goals:
            for npc_id in unique_ids:
                known_nodes[npc_id] = await _fetch_known_node_ids(session, npc_id)

            for row in rows:
                a_id = row["a"]["id"]
                b_id = row["b"]["id"]
                bonus = 0
                if goal_targets[a_id] & known_nodes.get(b_id, set()):
                    bonus += _GOAL_ALIGNMENT_BONUS
                if goal_targets[b_id] & known_nodes.get(a_id, set()):
                    bonus += _GOAL_ALIGNMENT_BONUS
                if bonus:
                    goal_alignment[(a_id, b_id)] = bonus

    def _sort_key(row: dict) -> tuple[float, str, str]:
        a_id = row["a"]["id"]
        b_id = row["b"]["id"]
        base = _pair_weight(row["a"]) + _pair_weight(row["b"])
        faction_weight = compute_faction_weight(
            sharer_faction_ids=set(row["a_faction_ids"]),
            receiver_faction_ids=set(row["b_faction_ids"]),
            best_standing=row["best_standing"],
            same_faction_boost=weight_config.same_faction_boost,
            allied_boost=weight_config.allied_boost,
            hostile_penalty=weight_config.hostile_penalty,
        )
        alignment_bonus = goal_alignment.get((a_id, b_id), 0)
        return (base * faction_weight + alignment_bonus, a_id, b_id)

    ranked = sorted(rows, key=_sort_key, reverse=True)
    return [
        (
            row["a"],
            row["b"],
            row["loc"],
            {
                "a_faction_ids": row["a_faction_ids"],
                "b_faction_ids": row["b_faction_ids"],
                "best_standing": row["best_standing"],
            },
        )
        for row in ranked[:max_pairs]
    ]
