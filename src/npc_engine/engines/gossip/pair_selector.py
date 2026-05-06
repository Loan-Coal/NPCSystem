"""
pair_selector.py - Selects gossip-eligible NPC pairs with deterministic ordering.

Does NOT: mutate knowledge edges.

Dependencies injected: AsyncSession.
"""

from neo4j import AsyncSession


CYPHER_GOSSIP_PAIRS = """
MATCH (a:Character)-[:LOCATED_AT]->(loc:Location)<-[:LOCATED_AT]-(b:Character)
WHERE a.id <> b.id
    AND a.is_player = false AND b.is_player = false
    AND a.is_active = true AND b.is_active = true
RETURN properties(a) AS a, properties(b) AS b, properties(loc) AS loc
"""


def _pair_weight(character: dict) -> int:
    return int(character.get("gossipy", 50))


async def select_pairs(session: AsyncSession, max_pairs: int) -> list[tuple[dict, dict, dict]]:
    """Return top-weighted directed gossip pairs sorted deterministically.

    Pairs are all co-located active non-player NPC combinations. Ranking uses
    the sum of both characters' ``gossipy`` attributes as the primary key, with
    character IDs as tiebreakers.

    Args:
        session: Active Neo4j async session.
        max_pairs: Maximum number of pairs to return.

    Returns:
        List of (sharer, receiver, location) property dicts, limited to max_pairs.
    """

    result = await session.run(CYPHER_GOSSIP_PAIRS)
    rows = [record.data() async for record in result]
    ranked = sorted(
        rows,
        key=lambda row: (_pair_weight(row["a"]) + _pair_weight(row["b"]), row["a"]["id"], row["b"]["id"]),
        reverse=True,
    )
    return [(row["a"], row["b"], row["loc"]) for row in ranked[:max_pairs]]
