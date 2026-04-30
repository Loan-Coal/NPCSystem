"""
schemas.py - Shared API request and response models.

Does NOT: execute graph or LLM logic.

Dependencies injected: None.
"""

from typing import Literal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


ActionType = Literal["speak", "gesture", "move", "attack", "give_item", "buy_item", "sell_item", "none"]
ExpressionType = Literal["neutral", "smile", "frown", "angry", "surprised", "sad"]
PlayerActionType = Literal["attack", "give_item", "steal", "help", "observe", "buy_item", "sell_item"]


class FrozenApiModel(BaseModel):
    """Shared immutable base model for API request/response contracts."""

    model_config = ConfigDict(frozen=True)


class DialogueRequest(FrozenApiModel):
    """Incoming dialogue request payload."""

    player_id: str
    npc_id: str
    player_message: str
    location_id: str | None = None
    session_id: str | None = None


class RelationDeltas(FrozenApiModel):
    """Per-turn relation delta outputs."""

    trust: int = Field(default=0, ge=-15, le=15)
    fear: int = Field(default=0, ge=-15, le=15)
    affection: int = Field(default=0, ge=-15, le=15)


class ActionModel(FrozenApiModel):
    """Action payload returned by dialogue engine."""

    type: ActionType = "speak"
    target_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class FacialExpressionModel(FrozenApiModel):
    """Facial expression payload returned by dialogue engine."""

    type: ExpressionType = "neutral"
    intensity: int = Field(default=0, ge=0, le=100)


class DialogueResponse(FrozenApiModel):
    """Final dialogue response contract for REST and WebSocket completion."""

    npc_response: str
    relation_deltas: RelationDeltas = Field(default_factory=RelationDeltas)
    mood_update: str | None = None
    action: ActionModel = Field(default_factory=ActionModel)
    facial_expression: FacialExpressionModel = Field(default_factory=FacialExpressionModel)
    session_id: str | None = None
    cached: bool = False
    degradation_level: str = "full"


class NPCStateResponse(FrozenApiModel):
    """Compact NPC state response model."""

    character: dict | None
    relations: list[dict]
    events: list[dict]


class EmotionResponse(FrozenApiModel):
    """Emotion response model."""

    npc_id: str
    label: str
    valence: int
    arousal: int
    updated_at: str


class ActionReportRequest(FrozenApiModel):
    """Game-reported player action against NPC."""

    player_id: str
    npc_id: str
    action_type: PlayerActionType
    intensity: int = Field(default=0, ge=0, le=100)
    counterparty_id: str | None = None
    currency_amount: int | None = Field(default=None, gt=0)
    currency_reason: str | None = None
    session_scope: str | None = None


class QuestObjectiveBody(FrozenApiModel):
    """One quest objective definition in API payloads."""

    objective_id: str
    target_count: int = Field(ge=1)


class QuestRewardItemBody(FrozenApiModel):
    """One item reward payload in quest API requests."""

    item_id: str
    quantity: int = Field(default=1, ge=1)


class QuestRewardCurrencyBody(FrozenApiModel):
    """Currency reward payload in quest API requests."""

    amount: int = Field(gt=0)


class QuestOfferRequest(FrozenApiModel):
    """Typed request body for quest offer lifecycle transition."""

    quest_id: str
    player_id: str
    title: str
    objectives: list[QuestObjectiveBody] = Field(min_length=1)
    item_rewards: list[QuestRewardItemBody] = Field(default_factory=list)
    currency_reward: QuestRewardCurrencyBody | None = None


class QuestAcceptRequest(FrozenApiModel):
    """Typed request body for quest acceptance transition."""

    quest_id: str
    player_id: str


class QuestObjectiveUpdateRequest(FrozenApiModel):
    """Typed request body for quest objective progress updates."""

    quest_id: str
    player_id: str
    objective_id: str
    progress_delta: int = 1


class QuestEvaluateRequest(FrozenApiModel):
    """Typed request body for quest completion evaluation."""

    quest_id: str
    player_id: str


class QuestRewardApplyRequest(FrozenApiModel):
    """Typed request body for quest reward application."""

    quest_id: str
    player_id: str

