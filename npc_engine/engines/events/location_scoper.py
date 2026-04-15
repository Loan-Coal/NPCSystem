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
    """Return location ids matching a template location tag."""

    result = await session.run(CYPHER_LOCATIONS_BY_TAG, location_tag=location_tag)
    return [str(record["id"]) async for record in result]
