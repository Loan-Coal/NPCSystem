"""
Module: gossip_queries
Layer: graph
Purpose: Read-side Cypher for gossip — event/trust/secret selection and pair scanning.
         Write-side queries live in graph.gossip_write_queries.
Does NOT: open transactions or write to the graph.
Dependencies injected: AsyncSession (passed per call)
Dependencies: neo4j, graph.labels, graph.relationships
Used by: engines/gossip/gossip_handler, engines/gossip/pair_selector
"""
from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.graph.labels import CHARACTER, EVENT, FACTION, LOCATION, SECRET
from npc_engine.graph.relationships import (
    KNOWS_ABOUT,
    KNOWS_SECRET,
    LOCATED_AT,
    MEMBER_OF,
    RELATES_TO,
    STANDS_WITH,
)

# Re-export write-side symbols so callers can import from one place.
from npc_engine.graph.gossip_write_queries import (  # noqa: F401
    fetch_relation_log,
    update_relation_log,
    write_knowledge_propagation,
    write_secret_propagation,
)

# ---------------------------------------------------------------------------
# Query constants
# ---------------------------------------------------------------------------

CYPHER_SELECT_EVENT = f"""
MATCH (a:{CHARACTER} {{id: $sharer_id}})-[k:{KNOWS_ABOUT}]->(e:{EVENT})
WHERE coalesce(k.knowledge_state, '') <> 'corrected'
RETURN e.id AS event_id,
       e.summary AS summary,
       e.severity AS severity,
       coalesce(e.is_canonical, false) AS is_canonical
ORDER BY coalesce(e.is_canonical, false) DESC,
         e.occurred_at DESC
LIMIT 1
"""

CYPHER_RELATION_TRUST = f"""
MATCH (a:{CHARACTER} {{id: $sharer_id}})-[r:{RELATES_TO}]->(b:{CHARACTER} {{id: $receiver_id}})
RETURN r.trust AS trust
"""

CYPHER_SELECT_SECRET = f"""
MATCH (a:{CHARACTER} {{id: $sharer_id}})-[:{KNOWS_SECRET}]->(s:{SECRET})
RETURN s.id AS secret_id, s.severity AS severity
ORDER BY s.severity DESC
LIMIT 1
"""

CYPHER_GOSSIP_PAIRS = f"""
MATCH (a:{CHARACTER})-[:{LOCATED_AT}]->(loc:{LOCATION})<-[:{LOCATED_AT}]-(b:{CHARACTER})
WHERE a.id <> b.id
    AND a.is_player = false AND b.is_player = false
    AND a.is_active = true AND b.is_active = true
OPTIONAL MATCH (a)-[:{MEMBER_OF}]->(fa:{FACTION})
WHERE fa.is_active = true
OPTIONAL MATCH (b)-[:{MEMBER_OF}]->(fb:{FACTION})
WHERE fb.is_active = true
OPTIONAL MATCH (fa)-[sw:{STANDS_WITH}]->(fb)
WITH a, b, loc,
     collect(DISTINCT fa.id) AS a_faction_ids,
     collect(DISTINCT fb.id) AS b_faction_ids,
     max(sw.standing) AS best_standing
RETURN properties(a) AS a, properties(b) AS b, properties(loc) AS loc,
       a_faction_ids, b_faction_ids, best_standing
"""

CYPHER_KNOWN_NODE_IDS = f"""
MATCH (c:{CHARACTER} {{id: $character_id}})-[:{KNOWS_ABOUT}]->(n)
RETURN n.id AS node_id
"""

# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------


async def select_gossip_event(session: AsyncSession, sharer_id: str) -> dict | None:
    """Return the best event the sharer knows about, or None.

    Canonical events are ordered first; corrected edges are excluded (SEV-09).

    Args:
        session: Active Neo4j async session.
        sharer_id: Character node ID of the gossip sharer.

    Returns:
        Dict with keys event_id, summary, severity, is_canonical, or None.
    """
    result = await session.run(CYPHER_SELECT_EVENT, sharer_id=sharer_id)
    record = await result.single()
    return record.data() if record is not None else None


async def select_relation_trust(
    session: AsyncSession, sharer_id: str, receiver_id: str
) -> int:
    """Return the trust value on the RELATES_TO edge between two characters.

    Args:
        session: Active Neo4j async session.
        sharer_id: Source character node ID.
        receiver_id: Target character node ID.

    Returns:
        Trust integer (0-100); defaults to 50 when no edge exists.
    """
    result = await session.run(
        CYPHER_RELATION_TRUST, sharer_id=sharer_id, receiver_id=receiver_id
    )
    record = await result.single()
    return int(record["trust"]) if record is not None else 50


async def select_gossip_secret(session: AsyncSession, sharer_id: str) -> dict | None:
    """Return the most severe secret the sharer holds, or None.

    Args:
        session: Active Neo4j async session.
        sharer_id: Character node ID of the gossip sharer.

    Returns:
        Dict with keys secret_id and severity, or None.
    """
    result = await session.run(CYPHER_SELECT_SECRET, sharer_id=sharer_id)
    record = await result.single()
    return record.data() if record is not None else None


async def fetch_gossip_pairs(session: AsyncSession) -> list[dict]:
    """Return all co-located active non-player NPC pairs as raw row dicts.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of dicts with keys a, b, loc, a_faction_ids, b_faction_ids, best_standing.
    """
    result = await session.run(CYPHER_GOSSIP_PAIRS)
    return [record.data() async for record in result]


async def fetch_known_node_ids(session: AsyncSession, character_id: str) -> set[str]:
    """Return the set of node IDs this character knows about via KNOWS_ABOUT edges.

    Args:
        session: Active Neo4j async session.
        character_id: Character node ID.

    Returns:
        Set of known node ID strings (empty strings excluded).
    """
    result = await session.run(CYPHER_KNOWN_NODE_IDS, character_id=character_id)
    return {record["node_id"] async for record in result if record["node_id"]}
