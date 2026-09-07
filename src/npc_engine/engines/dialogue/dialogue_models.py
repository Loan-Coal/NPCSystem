"""
dialogue_models.py - Internal dialogue domain models shared across the dialogue engine.
Layer: engines
Purpose: Internal dialogue domain models shared across the dialogue engine.

Does NOT: define HTTP transport schemas or route-layer concerns.

Dependencies injected: None.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic import StringConstraints

from npc_engine.config import MAX_PLAYER_MESSAGE_CHARS
from npc_engine.retrieval.context.context_receipt import ContextReceipt

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
    retrieval_profile: str | None = Field(
        default=None,
        description=(
            "Named retrieval configuration for this turn (the A/B switch). None uses the "
            "deployment default, Settings.RETRIEVAL_PROFILE. An undeclared name is a 4xx, "
            "never a silent fallback — a run must not be able to record a profile it did "
            "not use."
        ),
    )
    include_context_receipt: bool = Field(
        default=False,
        description=(
            "Return the assembled-context receipt on the response. Off by default so an "
            "ordinary reply is unchanged. Purely a reporting switch: it is never read by "
            "context assembly or prompt building, so it cannot alter generated text."
        ),
    )


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


class DialogueGeneration(FrozenDialogueModel):
    """The fields the LLM actually authors, and the grammar it is constrained by.

    Deliberately NOT a base class of, or subset derived from, DialogueResponse. That model
    is re-exported as the published HTTP schema (api/schemas.py) and pinned field-by-field
    by scripts/api_contract_baseline.json, and inheritance would reorder its properties.
    The duplication here is the price of leaving the public contract untouched.

    The seven fields this omits -- emotion, memories_recalled, session_id, cached,
    degradation_level, audio_bytes, context_receipt -- are all written by DialogueHandler
    after generation via model_copy, so any token the model spent on them was discarded.
    Dropping them also keeps ContextReceipt, DroppedItem and TierSpend out of the grammar.
    """

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
    action: ActionModel = Field(default_factory=ActionModel)
    facial_expression: FacialExpressionModel = Field(default_factory=FacialExpressionModel)
    learned_facts: tuple[str, ...] = Field(default=())


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
    learned_facts: tuple[str, ...] = Field(default=())
    memories_recalled: tuple[str, ...] = Field(
        default=(),
        description="Memory node IDs that appeared in the final context (ISSUE-107).",
    )
    session_id: str | None = None
    cached: bool = False
    degradation_level: str = "full"
    audio_bytes: bytes | None = None
    context_receipt: ContextReceipt | None = Field(
        default=None,
        description=(
            "What actually reached the model this turn: resolved retrieval profile, the "
            "context item keys assembled, per-tier token spend, and whether the prompt "
            "budget trimmed anything. Populated only when the request set "
            "include_context_receipt; None also on a cached-context turn, which has no "
            "assembly to report."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _derive_emotion(cls, data: object) -> object:
        """Populate emotion from mood_update when not explicitly provided."""
        if isinstance(data, dict) and not data.get("emotion"):
            data = dict(data)
            data["emotion"] = data.get("mood_update")
        return data
