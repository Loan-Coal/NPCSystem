"""
dialogue_models.py - Internal dialogue domain models shared across the dialogue engine.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: define HTTP transport schemas or route-layer concerns.

Dependencies injected: None.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic import StringConstraints

from npc_engine.config import MAX_PLAYER_MESSAGE_CHARS

# Strips transcript-style echo the LLM sometimes prefixes to npc_response.
# Matches: "player: <anything>\nnpc: " or "player: <anything>\n" (when no npc: label)
_ECHO_PREFIX_RE = re.compile(
    r"^player\s*:\s*.+?\n(?:npc\s*:\s*)?",
    re.IGNORECASE | re.DOTALL,
)


ActionType = Literal[
    "speak", "gesture", "move", "attack",
    "give_item", "buy_item", "sell_item", "none",
    "propose_trade", "propose_quest", "claim_completion",
]

_VALID_ACTION_TYPES: frozenset[str] = frozenset(ActionType.__args__)  # type: ignore[attr-defined]
ExpressionType = Literal["neutral", "smile", "frown", "angry", "surprised", "sad"]


class FrozenDialogueModel(BaseModel):
    """Shared immutable base for all dialogue domain models."""

    model_config = ConfigDict(frozen=True)


class DialogueRequest(FrozenDialogueModel):
    """Incoming dialogue request payload."""

    player_id: str
    npc_id: str
    player_message: Annotated[str, StringConstraints(max_length=MAX_PLAYER_MESSAGE_CHARS)]
    location_id: str | None = None
    session_id: str | None = None
    explicit_node_ids: tuple[str, ...] = Field(default_factory=tuple)


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

    @field_validator("type", mode="before")
    @classmethod
    def coerce_action_type(cls, v: object) -> object:
        if isinstance(v, str) and v not in _VALID_ACTION_TYPES:
            return "speak"
        return v


class FacialExpressionModel(FrozenDialogueModel):
    """Facial expression payload returned by the dialogue engine."""

    type: ExpressionType = "neutral"
    intensity: int = Field(default=0, ge=0, le=100)


class DialogueResponse(FrozenDialogueModel):
    """Final dialogue response contract for REST and WebSocket completion."""

    npc_response: str

    @field_validator("npc_response", mode="before")
    @classmethod
    def _strip_echo_prefix(cls, v: object) -> object:
        """Strip transcript-style 'player: .../npc: ' echo the LLM sometimes prepends."""
        if isinstance(v, str):
            stripped = _ECHO_PREFIX_RE.sub("", v).strip()
            if stripped:
                return stripped
        return v
    relation_deltas: RelationDeltas = Field(default_factory=RelationDeltas)
    mood_update: str | None = None
    emotion: str | None = None
    action: ActionModel = Field(default_factory=ActionModel)
    facial_expression: FacialExpressionModel = Field(default_factory=FacialExpressionModel)
    learned_facts: list[str] = Field(default_factory=list)
    session_id: str | None = None
    cached: bool = False
    degradation_level: str = "full"
    audio_bytes: bytes | None = None

    @model_validator(mode="before")
    @classmethod
    def _derive_emotion(cls, data: object) -> object:
        """Populate emotion from mood_update when not explicitly provided."""
        if isinstance(data, dict) and not data.get("emotion"):
            data = dict(data)
            data["emotion"] = data.get("mood_update")
        return data
