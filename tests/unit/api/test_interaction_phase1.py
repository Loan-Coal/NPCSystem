"""
test_interaction_phase1.py - Unit tests for Phase 1 of the interaction dispatch layer.

Covers:
- action_resolver: new proposal types pass through; unknown types coerce to none
- interaction dispatch: stub handler returns expected state for each proposal kind

Does NOT: write to graph, call the engine API, or touch Pygame.
"""

from __future__ import annotations

import pytest

from npc_engine.engines.dialogue.action_resolver import resolve_action, ALLOWED_ACTIONS
from npc_engine.engines.dialogue.dialogue_models import ActionModel
from npc_engine.engines.interaction.dispatch import dispatch_interaction
from npc_engine.engines.interaction.models import (
    InteractionProposal,
    STATUS_OPEN,
    STATUS_PENDING,
    UI_DIRECTIVE_STUB,
)

# ---------------------------------------------------------------------------
# action_resolver: new proposal types allowed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action_type", ["propose_trade", "propose_quest", "claim_completion"])
def test_resolve_action_allows_proposal_kinds(action_type: str) -> None:
    action = ActionModel(type=action_type, target_id="node_123", parameters={"x": 1})
    resolved = resolve_action(action)
    assert resolved.type == action_type
    assert resolved.target_id == "node_123"


def test_resolve_action_coerces_unknown_to_none() -> None:
    # ActionModel enforces a Literal type at construction; we bypass validation
    # here to test the coercion branch in resolve_action directly.
    action = ActionModel.model_construct(type="explode", target_id=None, parameters={})
    resolved = resolve_action(action)
    assert resolved.type == "none"


def test_allowed_actions_contains_new_types() -> None:
    assert "propose_trade" in ALLOWED_ACTIONS
    assert "propose_quest" in ALLOWED_ACTIONS
    assert "claim_completion" in ALLOWED_ACTIONS


# ---------------------------------------------------------------------------
# interaction dispatch: stub routing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["propose_quest", "claim_completion"])
def test_dispatch_stub_kinds_return_open_stub(kind: str) -> None:
    proposal = InteractionProposal(kind=kind, target_id=None)
    state = dispatch_interaction(proposal)
    assert state.status == STATUS_OPEN
    assert state.ui_directive == UI_DIRECTIVE_STUB


@pytest.mark.parametrize("kind", ["propose_trade", "give_item"])
def test_dispatch_trade_kinds_return_pending(kind: str) -> None:
    # EXP-40: propose_trade and give_item now delegate to MinimalSyncTradeHandler
    # which returns STATUS_PENDING (not the open stub) when item_type is provided.
    proposal = InteractionProposal(kind=kind, target_id="item_spice", payload={"item_type": "spice"})
    state = dispatch_interaction(proposal)
    assert state.status == STATUS_PENDING


def test_dispatch_unknown_kind_returns_none_directive() -> None:
    proposal = InteractionProposal(kind="speak", target_id=None)
    state = dispatch_interaction(proposal)
    assert state.status == STATUS_OPEN
    assert state.ui_directive == "none"

