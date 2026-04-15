"""
schemas.py - Shared API request and response models.

Does NOT: execute graph or LLM logic.

Dependencies injected: None.
"""

from typing import Literal

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
