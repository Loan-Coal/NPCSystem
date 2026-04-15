"""
world_state.py - Pydantic model for singleton world state node.

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
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)
