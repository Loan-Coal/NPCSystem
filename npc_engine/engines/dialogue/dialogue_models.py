"""
dialogue_models.py - Internal dialogue domain models shared across the dialogue engine.

Does NOT: define HTTP transport schemas or route-layer concerns.

Dependencies injected: None.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ActionType = Literal["speak", "gesture", "move", "attack", "give_item", "buy_item", "sell_item", "none"]
ExpressionType = Literal["neutral", "smile", "frown", "angry", "surprised", "sad"]


class FrozenDialogueModel(BaseModel):
    """Shared immutable base for all dialogue domain models."""

    model_config = ConfigDict(frozen=True)


class DialogueRequest(FrozenDialogueModel):
    """Incoming dialogue request payload."""

    player_id: str
    npc_id: str
    player_message: str
    location_id: str | None = None
    session_id: str | None = None


class RelationDeltas(FrozenDialogueModel):
    """Per-turn relation delta outputs from the LLM."""

    trust: int = Field(default=0, ge=-15, le=15)
    fear: int = Field(default=0, ge=-15, le=15)
    affection: int = Field(default=0, ge=-15, le=15)


class ActionModel(FrozenDialogueModel):
    """Action payload returned by the dialogue engine."""

    type: ActionType = "speak"
    target_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class FacialExpressionModel(FrozenDialogueModel):
    """Facial expression payload returned by the dialogue engine."""

    type: ExpressionType = "neutral"
    intensity: int = Field(default=0, ge=0, le=100)


class DialogueResponse(FrozenDialogueModel):
    """Final dialogue response contract for REST and WebSocket completion."""

    npc_response: str
    relation_deltas: RelationDeltas = Field(default_factory=RelationDeltas)
    mood_update: str | None = None
    action: ActionModel = Field(default_factory=ActionModel)
    facial_expression: FacialExpressionModel = Field(default_factory=FacialExpressionModel)
    session_id: str | None = None
    cached: bool = False
    degradation_level: str = "full"
