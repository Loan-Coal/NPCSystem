"""
action_resolver.py - Validates and normalizes candidate dialogue actions.

Does NOT: execute gameplay side effects.

Dependencies injected: None.
"""

from api.schemas import ActionModel


ALLOWED_ACTIONS = {"speak", "gesture", "move", "attack", "give_item", "buy_item", "sell_item", "none"}


def resolve_action(action: ActionModel) -> ActionModel:
    """Normalize invalid action values to safe no-op action."""

    if action.type not in ALLOWED_ACTIONS:
        return ActionModel(type="none", target_id=None, parameters={})
    return action
