"""
edge_schemas.py - Pydantic models for graph edge types and gossip distortion.

Does NOT: execute edge persistence queries.

Dependencies injected: None.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


KnowledgeState = Literal["knows", "rumor"]
DistortionType = Literal["omission", "exaggeration", "role_swap", "timeline_shift"]


class RelationDeltaEntry(BaseModel):
    """Single relation delta log entry."""

    tick_id: int
    cause_id: str
    deltas: dict[str, int]
    timestamp: datetime

    model_config = ConfigDict(frozen=True)


class RelationEdge(BaseModel):
    """Directed Character->Character relation edge model."""

    trust: int = Field(default=50, ge=0, le=100)
    fear: int = Field(default=50, ge=0, le=100)
    affection: int = Field(default=50, ge=0, le=100)
    interaction_count: int = 0
    delta_log: list[RelationDeltaEntry] = Field(default_factory=list)
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)
    relevance_score: float = 0.0

    model_config = ConfigDict(frozen=True)


class KnowsAboutEdge(BaseModel):
    """Character knowledge edge toward an event."""

    knowledge_state: KnowledgeState
    distortion_type: DistortionType | None = None
    distortion_level: int | None = Field(default=None, ge=0, le=100)
    distorted_summary: str | None = None
    learned_at_tick: int
    source_character_id: str | None = None

    model_config = ConfigDict(frozen=True)


class LocatedAtEdge(BaseModel):
    """Character location edge."""

    arrived_at: datetime
    is_permanent_resident: bool = False

    model_config = ConfigDict(frozen=True)


class ParticipatedInEdge(BaseModel):
    """Character participation edge for an event."""

    role: str
    participated_at: datetime

    model_config = ConfigDict(frozen=True)


class GossipDistortion(BaseModel):
    """Normalized distortion payload used by gossip engine."""

    summary: str
    distortion_type: DistortionType | None
    distortion_level: int = Field(ge=0, le=100)

    model_config = ConfigDict(frozen=True)
