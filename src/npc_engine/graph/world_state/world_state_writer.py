"""
world_state_writer.py - Persists WorldState updates and returns stored state.
Layer: graph
Purpose: Insert or update the singleton WorldState node (session and in-transaction variants).

Does NOT: decide event-driven world transitions (engines own that).

Dependencies injected: AsyncSession or AsyncTransaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.common.json_utils import dump_json, parse_json_list, parse_json_object
from npc_engine.world.world_state import (
    DEFAULT_GAME_TIME_SECONDS,
    DEFAULT_TICK_ID,
    WorldState,
)


# Monotonic clock guard (ISSUE-165). Several callers read a WorldState, model_copy it,
# and write it back (story_pacing_engine, event_emission_service), so a snapshot taken
# before a tick advance can be written back after one. Mirroring GameClock's "never moves
# backwards" invariant into Cypher makes that harmless, and protects writers not yet
# written. Defaults arrive as bound params so no literal is inlined in the query.
_CLOCK_MONOTONIC_SET = """    w.tick_id = CASE WHEN coalesce(w.tick_id, $default_tick_id) > $tick_id
                     THEN w.tick_id ELSE $tick_id END,
    w.game_time_seconds = CASE WHEN coalesce(w.game_time_seconds, $default_game_time_seconds) > $game_time_seconds
                               THEN w.game_time_seconds ELSE $game_time_seconds END,"""


CYPHER_MERGE_WORLD_STATE = f"""
MERGE (w:WorldState {{id: $id}})
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
{_CLOCK_MONOTONIC_SET}
    w.last_updated_at = datetime()
RETURN properties(w) AS world
"""


CYPHER_SET_WORLD_CLOCK = f"""
MERGE (w:WorldState {{id: $world_id}})
SET
{_CLOCK_MONOTONIC_SET}
    w.last_updated_at = datetime()
"""


def _world_state_write_params(world_state: WorldState) -> dict[str, Any]:
    """Build the parameter map for the MERGE query from a WorldState model.

    Args:
        world_state: Validated WorldState model whose fields are persisted.

    Returns:
        Mapping of Cypher parameter names to serialized values.
    """
    return {
        "id": world_state.id,
        "epoch": world_state.epoch,
        "faction_standings": dump_json(world_state.faction_standings),
        "active_conditions": dump_json(world_state.active_conditions),
        "weather": world_state.weather,
        "time_of_day": world_state.time_of_day,
        "year": world_state.year,
        "season": world_state.season,
        "day": world_state.day,
        "max_event_severity": world_state.max_event_severity,
        "quest_generation_rate": world_state.quest_generation_rate,
        "tick_id": world_state.tick_id,
        "game_time_seconds": world_state.game_time_seconds,
        "default_tick_id": DEFAULT_TICK_ID,
        "default_game_time_seconds": DEFAULT_GAME_TIME_SECONDS,
    }


def _world_state_from_record(payload: dict[str, Any], fallback: WorldState) -> WorldState:
    """Reconstruct a WorldState from a returned node-properties payload.

    Args:
        payload: ``properties(w)`` dict returned by the MERGE query.
        fallback: Values to fall back to for any missing field.

    Returns:
        WorldState reflecting the confirmed graph values, stamped with the write time.
    """
    return WorldState(
        id=payload.get("id", fallback.id),
        epoch=payload.get("epoch", fallback.epoch),
        faction_standings=cast(dict[str, int], parse_json_object(payload.get("faction_standings", {}))),
        active_conditions=cast(list[str], parse_json_list(payload.get("active_conditions", []))),
        weather=payload.get("weather", fallback.weather),
        time_of_day=payload.get("time_of_day", fallback.time_of_day),
        year=int(payload.get("year", fallback.year)),
        season=payload.get("season", fallback.season),
        day=int(payload.get("day", fallback.day)),
        max_event_severity=int(payload.get("max_event_severity", fallback.max_event_severity)),
        quest_generation_rate=float(payload.get("quest_generation_rate", fallback.quest_generation_rate)),
        tick_id=int(payload.get("tick_id", fallback.tick_id)),
        game_time_seconds=int(payload.get("game_time_seconds", fallback.game_time_seconds)),
        last_updated_at=datetime.now(timezone.utc),
    )


async def persist_clock_state(
    session: AsyncSession,
    *,
    world_id: str,
    tick_id: int,
    game_time_seconds: int,
) -> None:
    """Persist only the game-clock fields of the singleton WorldState node.

    Deliberately narrow: TickScheduler holds a WorldState snapshot read *before* the
    tick loop ran, so writing that whole snapshot back at finalize would clobber engines
    that mutated world state during the loop. Monotonic — never lowers a stored tick.

    Args:
        session: Active Neo4j async session used to run the MERGE query.
        world_id: Identifier of the singleton WorldState node.
        tick_id: Tick id to persist.
        game_time_seconds: Elapsed in-game seconds to persist.
    """
    await session.run(
        CYPHER_SET_WORLD_CLOCK,
        world_id=world_id,
        tick_id=tick_id,
        game_time_seconds=game_time_seconds,
        default_tick_id=DEFAULT_TICK_ID,
        default_game_time_seconds=DEFAULT_GAME_TIME_SECONDS,
    )


async def upsert_world_state_tx(tx: AsyncTransaction, world_state: WorldState) -> None:
    """Insert or update world state within an already-open transaction.

    Unlike upsert_world_state this variant does NOT return the confirmed state
    (the transaction has not committed yet). Callers that need the confirmed
    state must read it after the commit.

    Args:
        tx: Active Neo4j async transaction.
        world_state: Validated WorldState model whose fields are persisted.
    """
    await tx.run(CYPHER_MERGE_WORLD_STATE, **_world_state_write_params(world_state))


async def upsert_world_state(session: AsyncSession, world_state: WorldState) -> WorldState:
    """Insert or update singleton world state atomically.

    Args:
        session: Active Neo4j async session used to run the MERGE query.
        world_state: Validated WorldState model whose fields are persisted.

    Returns:
        WorldState reflecting the values confirmed by the graph after the write,
        or the input world_state unchanged if the query returns no record.
    """
    result = await session.run(CYPHER_MERGE_WORLD_STATE, **_world_state_write_params(world_state))
    record = await result.single()
    if record is None:
        return world_state
    return _world_state_from_record(dict(record["world"]), world_state)
