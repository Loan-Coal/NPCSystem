"""
Module: models
Layer: engines
Purpose: Shared data models for the interaction dispatch layer.
Does NOT: perform validation logic or call external services.
Dependencies injected: None.
Used by: engines.interaction.dispatch, demo_game.dialogue
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_PROPOSAL_KINDS = frozenset({"propose_trade", "propose_quest", "claim_completion", "give_item"})

UI_DIRECTIVE_NONE = "none"
UI_DIRECTIVE_STUB = "show_stub"
UI_DIRECTIVE_TRADE = "show_trade_panel"
UI_DIRECTIVE_QUEST = "show_quest_panel"
UI_DIRECTIVE_REWARD = "show_reward_overlay"

STATUS_OPEN = "open"
STATUS_PENDING = "pending"
STATUS_PENDING_CONFIRM = "pending_confirm"
STATUS_ACCEPTED = "accepted"
STATUS_DECLINED = "declined"


@dataclass(frozen=True)
class InteractionProposal:
    """An interaction surfaced by the LLM that requires deterministic adjudication.

    Carries the raw action from the dialogue engine. Handlers in the dispatch
    layer decide whether to open a negotiation, verify an objective, or refuse.

    Attributes:
        kind: Action type string — one of the proposal-class action types.
        target_id: Optional graph node ID the action targets (item, quest, NPC).
        payload: Free-form parameters dict from ActionModel.parameters.
    """

    kind: str
    target_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)

    def is_interaction_kind(self) -> bool:
        """Return True when kind is a proposal that the dispatch layer handles."""
        return self.kind in _PROPOSAL_KINDS


@dataclass(frozen=True)
class InteractionState:
    """Result returned by an interaction handler after processing one proposal.

    Attributes:
        status: Lifecycle status of the interaction session.
        ui_directive: Token telling the demo which panel/overlay to show.
        narration_hint: Optional hint for the NPC's next narrated response.
        data: Optional snapshot payload (e.g. NegotiationSession dict).
    """

    status: str
    ui_directive: str
    narration_hint: str | None = None
    data: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
