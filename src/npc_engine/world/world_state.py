"""
world_state.py - Pydantic model for singleton world state node.
Layer: services
Purpose: (auto-detected — review)

Does NOT: read or write world state from Neo4j.

Dependencies injected: None.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_graph_updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)
