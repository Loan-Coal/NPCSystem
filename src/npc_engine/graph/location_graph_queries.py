"""
Module: location_graph_queries
Layer: graph
Purpose: Graph queries for location connectivity — CONNECTS_TO edges and shortest-path traversal.
Does NOT: perform authentication or domain logic.
Dependencies: neo4j AsyncSession
Dependencies injected: AsyncSession (per call).
Used by: api/routes/location_graph, engines (future travel/supply-line queries)
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession


LOGGER = logging.getLogger(__name__)

CYPHER_CREATE_CONNECTION = """
MATCH (a:Location {id: $from_id}), (b:Location {id: $to_id})
MERGE (a)-[r1:CONNECTS_TO {kind: $kind}]->(b)
  ON CREATE SET r1.travel_cost = $travel_cost, r1.is_open = $is_open
  ON MATCH  SET r1.travel_cost = $travel_cost, r1.is_open = $is_open
MERGE (b)-[r2:CONNECTS_TO {kind: $kind}]->(a)
  ON CREATE SET r2.travel_cost = $travel_cost, r2.is_open = $is_open
  ON MATCH  SET r2.travel_cost = $travel_cost, r2.is_open = $is_open
RETURN r1, r2
"""

CYPHER_GET_CONNECTIONS = """
MATCH (src:Location {id: $location_id})-[r:CONNECTS_TO]->(dst:Location)
RETURN dst.id AS destination_id, dst.name AS destination_name,
       r.kind AS kind, r.travel_cost AS travel_cost,
       coalesce(r.is_open, true) AS is_open
ORDER BY r.travel_cost
"""

CYPHER_SHORTEST_PATH = """
MATCH p = shortestPath(
  (a:Location {id: $from_id})-[:CONNECTS_TO*]->(b:Location {id: $to_id})
)
RETURN [node IN nodes(p) | node.id] AS node_ids,
       [rel  IN relationships(p) | {kind: rel.kind, travel_cost: rel.travel_cost}] AS hops,
       reduce(cost = 0, r IN relationships(p) | cost + r.travel_cost) AS total_cost
"""

CYPHER_DELETE_CONNECTION = """
MATCH (a:Location {id: $from_id})-[r1:CONNECTS_TO]->(b:Location {id: $to_id})
DELETE r1
WITH a, b
MATCH (b)-[r2:CONNECTS_TO]->(a)
DELETE r2
"""


async def create_connection(
    session: AsyncSession,
    *,
    from_id: str,
    to_id: str,
    kind: str,
    travel_cost: int,
    is_open: bool = True,
) -> None:
    """Create bidirectional CONNECTS_TO edges between two locations.

    Both directions are created (A→B and B→A) with the same travel_cost and is_open.
    Safe to call multiple times — uses MERGE so existing edges are updated in-place.

    Args:
        session: Active Neo4j async session.
        from_id: ID of the source location node.
        to_id: ID of the destination location node.
        kind: Connection type (road | river | sea | secret).
        travel_cost: Ticks required to traverse this edge.
        is_open: Whether the connection is currently passable. Default True.

    Raises:
        ValueError: If from_id equals to_id.
    """
    if from_id == to_id:
        raise ValueError(f"Cannot connect a location to itself: {from_id!r}")
    await session.run(
        CYPHER_CREATE_CONNECTION,
        from_id=from_id,
        to_id=to_id,
        kind=kind,
        travel_cost=travel_cost,
        is_open=is_open,
    )
    LOGGER.debug("Created CONNECTS_TO %s <-> %s kind=%s cost=%d", from_id, to_id, kind, travel_cost)


async def get_connections_for_location(
    session: AsyncSession,
    location_id: str,
) -> list[dict]:
    """Return all outbound CONNECTS_TO edges from a location, ordered by travel cost.

    Args:
        session: Active Neo4j async session.
        location_id: ID of the source location.

    Returns:
        List of dicts with keys ``destination_id``, ``destination_name``,
        ``kind``, ``travel_cost``, ``is_open``.
    """
    result = await session.run(CYPHER_GET_CONNECTIONS, location_id=location_id)
    return [
        {
            "destination_id": rec["destination_id"],
            "destination_name": rec["destination_name"],
            "kind": rec["kind"],
            "travel_cost": rec["travel_cost"],
            "is_open": rec["is_open"],
        }
        async for rec in result
    ]


async def get_shortest_path(
    session: AsyncSession,
    from_location_id: str,
    to_location_id: str,
) -> dict | None:
    """Return the shortest path between two locations by hop count.

    Uses Cypher's built-in ``shortestPath()`` (fewest hops, not lowest cost).
    For lowest total travel_cost use the ``total_cost`` field to compare alternatives.

    Args:
        session: Active Neo4j async session.
        from_location_id: Starting location ID.
        to_location_id: Destination location ID.

    Returns:
        Dict with ``node_ids`` (list of location IDs in order), ``hops``
        (list of {kind, travel_cost} per edge), and ``total_cost``; or None if
        no path exists.
    """
    if from_location_id == to_location_id:
        return {"node_ids": [from_location_id], "hops": [], "total_cost": 0}

    result = await session.run(
        CYPHER_SHORTEST_PATH,
        from_id=from_location_id,
        to_id=to_location_id,
    )
    row = await result.single()
    if row is None:
        return None
    return {
        "node_ids": list(row["node_ids"]),
        "hops": [dict(h) for h in row["hops"]],
        "total_cost": int(row["total_cost"]),
    }


async def delete_connection(
    session: AsyncSession,
    *,
    from_id: str,
    to_id: str,
) -> None:
    """Remove the bidirectional CONNECTS_TO edges between two locations.

    Args:
        session: Active Neo4j async session.
        from_id: ID of one endpoint location.
        to_id: ID of the other endpoint location.
    """
    await session.run(CYPHER_DELETE_CONNECTION, from_id=from_id, to_id=to_id)
    LOGGER.debug("Deleted CONNECTS_TO %s <-> %s", from_id, to_id)


# ---------------------------------------------------------------------------
# PART_OF hierarchy queries (EXP-87)
# ---------------------------------------------------------------------------

CYPHER_GET_ANCESTORS = """
MATCH (n:Location {id: $location_id})-[:PART_OF*]->(a:Location)
RETURN a.id AS id
ORDER BY size((n)-[:PART_OF*]->(a))
"""

CYPHER_GET_DESCENDANTS = """
MATCH (d:Location)-[:PART_OF*]->(n:Location {id: $location_id})
RETURN d.id AS id
"""


async def get_ancestors(
    session: AsyncSession,
    *,
    location_id: str,
) -> list[str]:
    """Return an ordered list of ancestor location IDs from immediate parent to root.

    Traverses PART_OF edges upward. The first element is the immediate parent;
    the last element is the root node (a location with no PART_OF edge).

    Args:
        session: Active Neo4j async session.
        location_id: ID of the location whose ancestors to retrieve.

    Returns:
        Ordered list of ancestor location IDs, empty if the node is a root.
    """
    result = await session.run(CYPHER_GET_ANCESTORS, location_id=location_id)
    ids = [record["id"] async for record in result]
    await result.consume()
    return ids


async def get_descendants(
    session: AsyncSession,
    *,
    location_id: str,
) -> list[str]:
    """Return a flat list of all descendant location IDs.

    Traverses PART_OF edges downward (in reverse — children that point to
    this location as parent). All depths are included in a single flat list.

    Args:
        session: Active Neo4j async session.
        location_id: ID of the location whose descendants to retrieve.

    Returns:
        Flat list of descendant location IDs, empty if the node is a leaf.
    """
    result = await session.run(CYPHER_GET_DESCENDANTS, location_id=location_id)
    ids = [record["id"] async for record in result]
    await result.consume()
    return ids
