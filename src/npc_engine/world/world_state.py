"""
world_state.py - Pydantic model for singleton world state node.
Layer: services
Purpose: Define the frozen, immutable WorldState model shared across all engines (epoch, weather, faction standings, time-of-day).

Does NOT: read or write world state from Neo4j.

Dependencies injected: None.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


# Persisted game-clock seed (ISSUE-165). A world that has never ticked, and a graph
# written before the clock was persisted, both resolve to these values; GameClock.restore
# takes a max() so either case is a no-op rather than a rewind.
DEFAULT_TICK_ID: int = 0
DEFAULT_GAME_TIME_SECONDS: int = 0


class WorldState(BaseModel):
    """Global world state shared across all engines."""

    id: str = "world"
    epoch: str = "age_of_peace"
    faction_standings: dict[str, int] = Field(default_factory=dict)
    active_conditions: list[str] = Field(default_factory=list)
    weather: str = "clear"
    time_of_day: str = "morning"
    year: int = 1
    season: str = "spring"
    day: int = 1
    max_event_severity: int = 100
    quest_generation_rate: float = 1.0
    tick_id: int = DEFAULT_TICK_ID
    game_time_seconds: int = DEFAULT_GAME_TIME_SECONDS
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_graph_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)
