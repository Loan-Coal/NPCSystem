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


def _coerce_json_mapping(value: object) -> dict[str, int]:
    """Normalize stored mapping payloads to dict form."""

    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _coerce_json_list(value: object) -> list[str]:
    """Normalize stored list payloads to list form."""

    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return []
        if isinstance(parsed, list):
            return parsed
    return []


async def get_world_state(session: AsyncSession, world_id: str = "world") -> WorldState:
    """Return world state or default model when node does not exist."""

    result = await session.run(CYPHER_GET_WORLD_STATE, world_id=world_id)
    record = await result.single()
    if record is None:
        return WorldState()
    payload = dict(record["world"])
    payload["faction_standings"] = _coerce_json_mapping(payload.get("faction_standings", {}))
    payload["active_conditions"] = _coerce_json_list(payload.get("active_conditions", []))
    for field_name in ("last_updated_at", "last_graph_updated_at"):
        if field_name in payload:
            payload[field_name] = _coerce_datetime(payload[field_name])
    return WorldState(**payload)
