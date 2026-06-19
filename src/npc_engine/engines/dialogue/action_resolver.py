"""
action_resolver.py - Validates and normalizes candidate dialogue actions.
Layer: engines
Purpose: Validates and normalizes candidate dialogue actions.

Does NOT: execute gameplay side effects.

Dependencies injected: None.
"""

from __future__ import annotations

from typing import Any

from npc_engine.engines.dialogue.dialogue_models import ActionModel


ALLOWED_ACTIONS = {
    "speak", "gesture", "move", "attack",
    "give_item", "buy_item", "sell_item", "none",
    "propose_trade", "propose_quest", "claim_completion",
}


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


def check_give_item_ownership(
    action: ActionModel,
    owned_items: list[dict[str, Any]],
) -> ActionModel:
    """Verify the NPC owns the item before allowing a give_item action.

    When the action type is ``give_item`` and the item named in
    ``action.parameters["item_name"]`` is not found among the NPC's
    owned items, the action is resolved to a ``type="none"`` no-op.

    Args:
        action: Resolved action model (should already have passed resolve_action).
        owned_items: List of item dicts from get_items_for_character, keyed by
            ``name`` and ``id``.

    Returns:
        The original action if ownership is confirmed or the action is not
        ``give_item``; otherwise a ``type="none"`` no-op.
    """
    if action.type != "give_item":
        return action

    item_name = action.parameters.get("item_name", "")
    item_id = action.parameters.get("item_id", "")

    owned_names = {item["name"] for item in owned_items}
    owned_ids = {item["id"] for item in owned_items}

    if item_name in owned_names or item_id in owned_ids:
        return action

    return ActionModel(
        type="none",
        target_id=None,
        parameters={"ignored_reason": "npc_does_not_own_item"},
    )
