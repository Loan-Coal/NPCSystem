"""
location_scoper.py - Resolves candidate locations for event templates.

Does NOT: create events or awareness edges.

Dependencies injected: AsyncSession.
"""

from neo4j import AsyncSession


CYPHER_LOCATIONS_BY_TAG = """
MATCH (loc:Location {location_tag: $location_tag})
RETURN loc.id AS id
"""


async def resolve_locations(session: AsyncSession, location_tag: str) -> list[str]:
    """Return location IDs matching the given template location tag.

    Args:
        session: Active Neo4j async session.
        location_tag: Location tag string to match against Location nodes.

    Returns:
        List of location ID strings; empty list if no matching locations exist.
    """

    result = await session.run(CYPHER_LOCATIONS_BY_TAG, location_tag=location_tag)
    return [str(record["id"]) async for record in result]
