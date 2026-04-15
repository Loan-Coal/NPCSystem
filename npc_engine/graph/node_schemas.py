"""
node_schemas.py - Pydantic models for graph node types.

Does NOT: run Cypher queries or persist graph data.

Dependencies injected: None.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CharacterNode(BaseModel):
    """Character node model for NPCs and players."""

    id: str
    name: str
    archetype: str
    faction: str | None = None
    biography: str
    current_location_id: str
    is_player: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    gossipy: int = Field(default=50, ge=0, le=100)
    credulity: int = Field(default=50, ge=0, le=100)
    honesty: int = Field(default=50, ge=0, le=100)
    current_mood: str | None = "neutral"

    model_config = ConfigDict(frozen=True)


class EventNode(BaseModel):
    """Event node model describing world events."""

    id: str
    summary: str
    severity: int = Field(ge=0, le=100)
    location_id: str
    occurred_at: datetime
    tick_id: int
    participants: list[str] = Field(default_factory=list)
    event_type: str
    is_public: bool = True

    model_config = ConfigDict(frozen=True)


class LocationNode(BaseModel):
    """Location node model for world places."""

    id: str
    name: str
    region: str | None = None
    location_tag: str
    descriptor: str

    model_config = ConfigDict(frozen=True)
