"""
world_reader.py - Fetches the singleton WorldState node from Neo4j.

Does NOT: update world state values.

Dependencies injected: AsyncSession.
"""

import json

from neo4j import AsyncSession

from world.world_state import WorldState


CYPHER_GET_WORLD_STATE = """
MATCH (w:WorldState {id: $world_id})
RETURN properties(w) AS world
"""


async def get_world_state(session: AsyncSession, world_id: str = "world") -> WorldState:
    """Return world state or default model when node does not exist."""

    result = await session.run(CYPHER_GET_WORLD_STATE, world_id=world_id)
    record = await result.single()
    if record is None:
        return WorldState()
    payload = dict(record["world"])
    payload["faction_standings"] = json.loads(payload.get("faction_standings", "{}"))
    payload["active_conditions"] = json.loads(payload.get("active_conditions", "[]"))
    return WorldState(**payload)
