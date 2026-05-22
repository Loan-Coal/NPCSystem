"""
world_reader.py - Fetches the singleton WorldState node from Neo4j.

Does NOT: update world state values.

Dependencies injected: AsyncSession.
"""

from datetime import datetime
from typing import cast

from neo4j import AsyncSession

from npc_engine.common.json_utils import parse_json_list, parse_json_object
from npc_engine.world.world_state import WorldState


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
    """Return world state or default model when node does not exist.

    Args:
        session: Active Neo4j async session used to run the read query.
        world_id: Node identifier for the singleton world state (default "world").

    Returns:
        Populated WorldState from the graph, or a default WorldState if the node is absent.
    """

    result = await session.run(CYPHER_GET_WORLD_STATE, world_id=world_id)
    record = await result.single()
    await result.consume()
    if record is None:
        return WorldState()
    payload = dict(record["world"])
    payload["faction_standings"] = cast(dict[str, int], parse_json_object(payload.get("faction_standings", {})))
    payload["active_conditions"] = cast(list[str], parse_json_list(payload.get("active_conditions", [])))
    for field_name in ("last_updated_at", "last_graph_updated_at"):
        if field_name in payload:
            payload[field_name] = _coerce_datetime(payload[field_name])
    return WorldState(**payload)
