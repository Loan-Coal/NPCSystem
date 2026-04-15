"""
world_reader.py - Fetches the singleton WorldState node from Neo4j.

Does NOT: update world state values.

Dependencies injected: AsyncSession.
"""

import json
from datetime import datetime

from neo4j import AsyncSession

from world.world_state import WorldState


CYPHER_GET_WORLD_STATE = """
MATCH (w:WorldState {id: $world_id})
RETURN properties(w) AS world
"""


def _coerce_datetime(value: object) -> object:
    """Convert Neo4j temporal values to Python datetime when available."""

    if isinstance(value, datetime):
        return value
    to_native = getattr(value, "to_native", None)
    if callable(to_native):
        native = to_native()
        if isinstance(native, datetime):
            return native
    return value


async def get_world_state(session: AsyncSession, world_id: str = "world") -> WorldState:
    """Return world state or default model when node does not exist."""

    result = await session.run(CYPHER_GET_WORLD_STATE, world_id=world_id)
    record = await result.single()
    if record is None:
        return WorldState()
    payload = dict(record["world"])
    payload["faction_standings"] = json.loads(payload.get("faction_standings", "{}"))
    payload["active_conditions"] = json.loads(payload.get("active_conditions", "[]"))
    if "last_updated_at" in payload:
        payload["last_updated_at"] = _coerce_datetime(payload["last_updated_at"])
    return WorldState(**payload)
