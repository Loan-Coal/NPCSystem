"""
world_writer.py - Persists WorldState updates and returns stored state.
Layer: services
Purpose: (auto-detected — review)

Does NOT: decide event-driven world transitions.

Dependencies injected: AsyncSession or AsyncTransaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.common.json_utils import dump_json, parse_json_list, parse_json_object
from npc_engine.world.world_state import WorldState


CYPHER_MERGE_WORLD_STATE = """
MERGE (w:WorldState {id: $id})
SET w.epoch = $epoch,
    w.faction_standings = $faction_standings,
    w.active_conditions = $active_conditions,
    w.weather = $weather,
    w.time_of_day = $time_of_day,
    w.year = $year,
    w.season = $season,
    w.day = $day,
    w.max_event_severity = $max_event_severity,
    w.quest_generation_rate = $quest_generation_rate,
    w.last_updated_at = datetime()
RETURN properties(w) AS world
"""


async def upsert_world_state_tx(tx: AsyncTransaction, world_state: WorldState) -> None:
    """Insert or update world state within an already-open transaction.

    Unlike upsert_world_state this variant does NOT return the confirmed state
    (the transaction has not committed yet). Callers that need the confirmed
    state must read it after the commit.

    Args:
        tx: Active Neo4j async transaction.
        world_state: Validated WorldState model whose fields are persisted.
    """
    await tx.run(
        CYPHER_MERGE_WORLD_STATE,
        id=world_state.id,
        epoch=world_state.epoch,
        faction_standings=dump_json(world_state.faction_standings),
        active_conditions=dump_json(world_state.active_conditions),
        weather=world_state.weather,
        time_of_day=world_state.time_of_day,
        year=world_state.year,
        season=world_state.season,
        day=world_state.day,
        max_event_severity=world_state.max_event_severity,
        quest_generation_rate=world_state.quest_generation_rate,
    )


async def upsert_world_state(session: AsyncSession, world_state: WorldState) -> WorldState:
    """Insert or update singleton world state atomically.

    Args:
        session: Active Neo4j async session used to run the MERGE query.
        world_state: Validated WorldState model whose fields are persisted.

    Returns:
        WorldState reflecting the values confirmed by the graph after the write,
        or the input world_state unchanged if the query returns no record.
    """

    result = await session.run(
        CYPHER_MERGE_WORLD_STATE,
        id=world_state.id,
        epoch=world_state.epoch,
        faction_standings=dump_json(world_state.faction_standings),
        active_conditions=dump_json(world_state.active_conditions),
        weather=world_state.weather,
        time_of_day=world_state.time_of_day,
        year=world_state.year,
        season=world_state.season,
        day=world_state.day,
        max_event_severity=world_state.max_event_severity,
        quest_generation_rate=world_state.quest_generation_rate,
    )
    record = await result.single()
    if record is None:
        return world_state
    payload = dict(record["world"])
    return WorldState(
        id=payload.get("id", world_state.id),
        epoch=payload.get("epoch", world_state.epoch),
        faction_standings=cast(dict[str, int], parse_json_object(payload.get("faction_standings", {}))),
        active_conditions=cast(list[str], parse_json_list(payload.get("active_conditions", []))),
        weather=payload.get("weather", world_state.weather),
        time_of_day=payload.get("time_of_day", world_state.time_of_day),
        year=int(payload.get("year", world_state.year)),
        season=payload.get("season", world_state.season),
        day=int(payload.get("day", world_state.day)),
        max_event_severity=int(payload.get("max_event_severity", world_state.max_event_severity)),
        quest_generation_rate=float(payload.get("quest_generation_rate", world_state.quest_generation_rate)),
        last_updated_at=datetime.now(timezone.utc),
    )
