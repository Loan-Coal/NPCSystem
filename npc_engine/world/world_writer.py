"""
world_writer.py - Persists WorldState updates and returns stored state.

Does NOT: decide event-driven world transitions.

Dependencies injected: AsyncSession.
"""

import json
from datetime import datetime, timezone

from neo4j import AsyncSession

from world.world_state import WorldState


CYPHER_MERGE_WORLD_STATE = """
MERGE (w:WorldState {id: $id})
SET w.epoch = $epoch,
    w.faction_standings = $faction_standings,
    w.active_conditions = $active_conditions,
    w.weather = $weather,
    w.last_updated_at = datetime()
RETURN properties(w) AS world
"""


async def upsert_world_state(session: AsyncSession, world_state: WorldState) -> WorldState:
    """Insert or update singleton world state atomically."""

    result = await session.run(
        CYPHER_MERGE_WORLD_STATE,
        id=world_state.id,
        epoch=world_state.epoch,
        faction_standings=json.dumps(world_state.faction_standings),
        active_conditions=json.dumps(world_state.active_conditions),
        weather=world_state.weather,
    )
    record = await result.single()
    if record is None:
        return world_state
    payload = dict(record["world"])
    return WorldState(
        id=payload.get("id", world_state.id),
        epoch=payload.get("epoch", world_state.epoch),
        faction_standings=json.loads(payload.get("faction_standings", "{}")),
        active_conditions=json.loads(payload.get("active_conditions", "[]")),
        weather=payload.get("weather", world_state.weather),
        last_updated_at=datetime.now(timezone.utc),
    )
