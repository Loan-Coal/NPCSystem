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
    counterparty_id: str | None = None
    currency_amount: int | None = Field(default=None, gt=0)
    currency_reason: str | None = None
    session_scope: str | None = None

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


class QuestObjectiveBody(BaseModel):
    """One quest objective definition in API payloads."""

    objective_id: str
    target_count: int = Field(ge=1)

    model_config = ConfigDict(frozen=True)


class QuestRewardItemBody(BaseModel):
    """One item reward payload in quest API requests."""

    item_id: str
    quantity: int = Field(default=1, ge=1)

    model_config = ConfigDict(frozen=True)


class QuestRewardCurrencyBody(BaseModel):
    """Currency reward payload in quest API requests."""

    amount: int = Field(gt=0)

    model_config = ConfigDict(frozen=True)


class QuestOfferRequest(BaseModel):
    """Typed request body for quest offer lifecycle transition."""

    quest_id: str
    player_id: str
    title: str
    objectives: list[QuestObjectiveBody] = Field(min_length=1)
    item_rewards: list[QuestRewardItemBody] = Field(default_factory=list)
    currency_reward: QuestRewardCurrencyBody | None = None

    model_config = ConfigDict(frozen=True)


class QuestAcceptRequest(BaseModel):
    """Typed request body for quest acceptance transition."""

    quest_id: str
    player_id: str

    model_config = ConfigDict(frozen=True)


class QuestObjectiveUpdateRequest(BaseModel):
    """Typed request body for quest objective progress updates."""

    quest_id: str
    player_id: str
    objective_id: str
    progress_delta: int = 1

    model_config = ConfigDict(frozen=True)


class QuestEvaluateRequest(BaseModel):
    """Typed request body for quest completion evaluation."""

    quest_id: str
    player_id: str

    model_config = ConfigDict(frozen=True)


class QuestRewardApplyRequest(BaseModel):
    """Typed request body for quest reward application."""

    quest_id: str
    player_id: str

    model_config = ConfigDict(frozen=True)
