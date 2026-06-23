"""
Module: memory_temporal
Layer: retrieval
Purpose: Annotate NPC memories with a coarse temporal 'age' (recent vs long_past)
         relative to the current world game-time, so the dialogue prompt can frame
         them as past recollections rather than current events (S26.2, ISSUE-093).
Does NOT: query Neo4j, call the LLM, or mutate its inputs.
Dependencies injected: current game-time (TimePoint), supplied by the caller.
Used by: retrieval.context_builder
"""

from __future__ import annotations

import json
from typing import Any

from npc_engine.world.time_utils import TimePoint, total_days

# A memory whose event/record time is at least one in-world year before "now" is
# framed as a long-past recollection (forward-compatible with S26.3's is_historical).
MEMORY_LONG_PAST_GAME_DAYS = 365

AGE_KEY = "age"
AGE_RECENT = "recent"
AGE_LONG_PAST = "long_past"


def _memory_time(memory: dict[str, Any]) -> TimePoint | None:
    """Parse a memory's event time (occurred_at preferred, else created_at)."""
    raw = memory.get("occurred_at_game_time") or memory.get("created_at_game_time")
    if raw is None:
        return None
    try:
        gt = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(gt, dict):
            return None
        return TimePoint(
            year=int(gt.get("year", 0)),
            season=str(gt.get("season", "spring")),
            day=int(gt.get("day", 1)),
            time_of_day=str(gt.get("time_of_day", "morning")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _classify_age(memory: dict[str, Any], current_game_time: TimePoint) -> str:
    """Classify one memory as recent or long_past relative to the current game-time."""
    if memory.get("is_historical"):
        return AGE_LONG_PAST
    node_tp = _memory_time(memory)
    if node_tp is None:
        return AGE_RECENT
    age_days = total_days(current_game_time) - total_days(node_tp)
    return AGE_LONG_PAST if age_days >= MEMORY_LONG_PAST_GAME_DAYS else AGE_RECENT


def annotate_memory_ages(
    memories: list[dict[str, Any]], current_game_time: TimePoint | None
) -> list[dict[str, Any]]:
    """Return a copy of memories with a coarse 'age' field added to each. Pure.

    When current_game_time is None the memories are returned as a shallow copy with no
    'age' key (the prompt simply omits the recency hint). Input dicts are never mutated.

    Args:
        memories: Memory dicts (content, vividness, created_at_game_time, …).
        current_game_time: The world's current in-game time, or None.
    Returns:
        New list of memory dicts, each with an 'age' of "recent" or "long_past"
        (omitted when current_game_time is None).
    """
    if current_game_time is None:
        return [dict(memory) for memory in memories]
    return [
        {**memory, AGE_KEY: _classify_age(memory, current_game_time)}
        for memory in memories
    ]
