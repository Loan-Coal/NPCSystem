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


def _pair_weight(character: dict) -> int:
    return int(character.get("gossipy", 50))


async def select_pairs(
    session: AsyncSession,
    max_pairs: int,
    weight_config: GossipWeightConfig,
) -> list[tuple[dict, dict, dict, dict]]:
    """Return top-weighted directed gossip pairs sorted deterministically.

    Pairs are all co-located active non-player NPC combinations. Ranking uses
    the sum of both characters' ``gossipy`` attributes multiplied by the faction
    weight as the primary key, with character IDs as tiebreakers.

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

    def _sort_key(row: dict) -> tuple[float, str, str]:
        base = _pair_weight(row["a"]) + _pair_weight(row["b"])
        faction_weight = compute_faction_weight(
            sharer_faction_ids=set(row["a_faction_ids"]),
            receiver_faction_ids=set(row["b_faction_ids"]),
            best_standing=row["best_standing"],
            same_faction_boost=weight_config.same_faction_boost,
            allied_boost=weight_config.allied_boost,
            hostile_penalty=weight_config.hostile_penalty,
        )
        return (base * faction_weight, row["a"]["id"], row["b"]["id"])

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
