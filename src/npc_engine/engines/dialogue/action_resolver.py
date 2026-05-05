"""
action_resolver.py - Validates and normalizes candidate dialogue actions.

Does NOT: execute gameplay side effects.

Dependencies injected: None.
"""

from npc_engine.engines.dialogue.dialogue_models import ActionModel


ALLOWED_ACTIONS = {"speak", "gesture", "move", "attack", "give_item", "buy_item", "sell_item", "none"}


def resolve_action(action: ActionModel) -> ActionModel:
    """Normalize unrecognised action types to a safe no-op action.

    Args:
        action: Raw action model from LLM output.

    Returns:
        The original action if its type is in ALLOWED_ACTIONS, otherwise a
        ``type="none"`` no-op action with null target and empty parameters.
    """

    if action.type not in ALLOWED_ACTIONS:
        return ActionModel(type="none", target_id=None, parameters={})
    return action
