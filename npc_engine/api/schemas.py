"""
schemas.py - Shared API request and response models.

Does NOT: execute graph or LLM logic.

Dependencies injected: None.
"""

from typing import Literal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


ActionType = Literal["speak", "gesture", "move", "attack", "give_item", "none"]
ExpressionType = Literal["neutral", "smile", "frown", "angry", "surprised", "sad"]
PlayerActionType = Literal["attack", "give_item", "steal", "help", "observe"]


class DialogueRequest(BaseModel):
    """Incoming dialogue request payload."""

    player_id: str
    npc_id: str
    player_message: str
    location_id: str | None = None
    session_id: str | None = None

    model_config = ConfigDict(frozen=True)


class RelationDeltas(BaseModel):
    """Per-turn relation delta outputs."""

    trust: int = Field(default=0, ge=-15, le=15)
    fear: int = Field(default=0, ge=-15, le=15)
    affection: int = Field(default=0, ge=-15, le=15)

    model_config = ConfigDict(frozen=True)


class ActionModel(BaseModel):
    """Action payload returned by dialogue engine."""

    type: ActionType = "speak"
    target_id: str | None = None
    parameters: dict = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class FacialExpressionModel(BaseModel):
    """Facial expression payload returned by dialogue engine."""

    type: ExpressionType = "neutral"
    intensity: int = Field(default=0, ge=0, le=100)

    model_config = ConfigDict(frozen=True)


class DialogueResponse(BaseModel):
    """Final dialogue response contract for REST and WebSocket completion."""

    npc_response: str
    relation_deltas: RelationDeltas = Field(default_factory=RelationDeltas)
    mood_update: str | None = None
    action: ActionModel = Field(default_factory=ActionModel)
    facial_expression: FacialExpressionModel = Field(default_factory=FacialExpressionModel)
    session_id: str | None = None
    cached: bool = False

    model_config = ConfigDict(frozen=True)


class NPCStateResponse(BaseModel):
    """Compact NPC state response model."""

    character: dict | None
    relations: list[dict]
    events: list[dict]


class EmotionResponse(BaseModel):
    """Emotion response model."""

    npc_id: str
    label: str
    valence: int
    arousal: int
    updated_at: str


class ActionReportRequest(BaseModel):
    """Game-reported player action against NPC."""

    player_id: str
    npc_id: str
    action_type: PlayerActionType
    intensity: int = Field(default=0, ge=0, le=100)

    model_config = ConfigDict(frozen=True)


class MutationMeta(BaseModel):
    """Audit metadata required for graph mutation requests."""

    request_id: str
    actor_id: str
    reason: str

    model_config = ConfigDict(frozen=True)


class CharacterPatchBody(BaseModel):
    """Typed PATCH body for Character mutations."""

    name: str | None = None
    archetype: str | None = None
    faction: str | None = None
    biography: str | None = None
    current_location_id: str | None = None
    gossipy: int | None = Field(default=None, ge=0, le=100)
    credulity: int | None = Field(default=None, ge=0, le=100)
    honesty: int | None = Field(default=None, ge=0, le=100)
    current_mood: str | None = None
    is_active: bool | None = None
    extension_fields: dict[str, Any] | None = None
    meta: MutationMeta

    model_config = ConfigDict(frozen=True)


class EventPatchBody(BaseModel):
    """Typed PATCH body for Event mutations."""

    summary: str | None = None
    severity: int | None = Field(default=None, ge=0, le=100)
    is_public: bool | None = None
    extension_fields: dict[str, Any] | None = None
    meta: MutationMeta

    model_config = ConfigDict(frozen=True)


class LocationPatchBody(BaseModel):
    """Typed PATCH body for Location mutations."""

    name: str | None = None
    region: str | None = None
    location_tag: str | None = None
    descriptor: str | None = None
    extension_fields: dict[str, Any] | None = None
    meta: MutationMeta

    model_config = ConfigDict(frozen=True)


class WorldStatePatchBody(BaseModel):
    """Typed PATCH body for WorldState with full-replace JSON semantics."""

    epoch: str | None = None
    faction_standings: dict[str, int] | None = None
    active_conditions: list[str] | None = None
    weather: str | None = None
    extension_fields: dict[str, Any] | None = None
    meta: MutationMeta

    model_config = ConfigDict(frozen=True)


class CharacterMoveBody(BaseModel):
    """Typed request body for atomic character move."""

    location_id: str
    meta: MutationMeta

    model_config = ConfigDict(frozen=True)


class RelatesToEdgeBody(BaseModel):
    """Typed request body for RELATES_TO edge upsert."""

    src_id: str
    dst_id: str
    trust: int = Field(default=50, ge=0, le=100)
    fear: int = Field(default=50, ge=0, le=100)
    affection: int = Field(default=50, ge=0, le=100)
    meta: MutationMeta

    model_config = ConfigDict(frozen=True)


class KnowsAboutEdgeBody(BaseModel):
    """Typed request body for KNOWS_ABOUT edge upsert."""

    character_id: str
    event_id: str
    knowledge_state: Literal["knows", "rumor"]
    distortion_type: str | None = None
    distortion_level: int | None = Field(default=None, ge=0, le=100)
    distorted_summary: str | None = None
    learned_at_tick: int
    source_character_id: str | None = None
    meta: MutationMeta

    model_config = ConfigDict(frozen=True)


class LocatedAtEdgeBody(BaseModel):
    """Typed request body for LOCATED_AT edge upsert."""

    character_id: str
    location_id: str
    is_permanent_resident: bool = False
    meta: MutationMeta

    model_config = ConfigDict(frozen=True)


class ParticipatedInEdgeBody(BaseModel):
    """Typed request body for PARTICIPATED_IN edge upsert."""

    character_id: str
    event_id: str
    role: str
    meta: MutationMeta

    model_config = ConfigDict(frozen=True)
