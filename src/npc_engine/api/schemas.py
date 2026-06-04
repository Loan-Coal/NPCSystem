"""
schemas.py - Shared API request and response models.
Layer: api
Purpose: (auto-detected — review)

Does NOT: execute graph or LLM logic.

Dependencies injected: None.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from npc_engine.engines.dialogue.dialogue_models import (
    ActionModel,
    ActionType,
    DialogueRequest,
    DialogueResponse,
    ExpressionType,
    FacialExpressionModel,
    FrozenDialogueModel,
    RelationDeltas,
)

PlayerActionType = Literal["attack", "give_item", "steal", "help", "observe", "buy_item", "sell_item"]


class FrozenApiModel(FrozenDialogueModel):
    """Frozen base class for all API schema models.

    Inherits model_config from FrozenDialogueModel (frozen=True, extra='forbid').
    Using a named class rather than a value alias allows mypy to treat it as a
    valid base class and enables proper OpenAPI schema generation.
    """

__all__ = [
    "ActionModel",
    "ActionType",
    "DialogueRequest",
    "DialogueResponse",
    "ExpressionType",
    "FacialExpressionModel",
    "FrozenApiModel",
    "RelationDeltas",
    "PlayerActionType",
    "FrozenApiModel",
    "NPCStateResponse",
    "EmotionResponse",
    "ActionReportRequest",
    "QuestObjectiveBody",
    "QuestRewardItemBody",
    "QuestRewardCurrencyBody",
    "QuestOfferRequest",
    "QuestAcceptRequest",
    "QuestObjectiveUpdateRequest",
    "QuestEvaluateRequest",
    "QuestRewardApplyRequest",
]


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
    """One quest objective definition in API payloads.

    Attributes:
        objective_id: Stable identifier for this objective.
        target_count: How many times the objective must be satisfied.
        objective_type: Verification strategy — ``"deliver"`` checks HAS_ITEM.
        target_id: Graph node ID the verifier checks against.
    """

    objective_id: str
    target_count: int = Field(ge=1)
    objective_type: Literal["deliver", "kill", "visit", "talk"] = "deliver"
    target_id: str | None = None


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
    reward_source_id: str = "system"


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

