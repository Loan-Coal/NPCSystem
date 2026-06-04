"""
location_scoper.py - Resolves candidate locations for event templates.

Does NOT: create events or awareness edges.

Dependencies injected: AsyncSession (via graph.event_queries.get_locations_by_tag).
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.graph.event_queries import get_locations_by_tag


async def resolve_locations(session: AsyncSession, location_tag: str) -> list[str]:
    """Return location IDs matching the given template location tag.

    Delegates to graph.event_queries.get_locations_by_tag.

    Args:
        session: Active Neo4j async session.
        location_tag: Location tag string to match against Location nodes.

    Returns:
        List of location ID strings; empty list if no matching locations exist.
    """
    return await get_locations_by_tag(session=session, location_tag=location_tag)
