"""
action_helpers.py - Pure helpers for /action route branching and payload shaping.

Does NOT: execute graph writes.

Dependencies injected: None.
"""

from datetime import datetime, timezone

from npc_engine.api.schemas import PlayerActionType


MAX_ACTION_DELTA = 15

_ACTION_DELTA_MULTIPLIERS: dict[PlayerActionType, tuple[int, int, int]] = {
    "help": (1, -1, 1),
    "attack": (-1, 1, -1),
    "give_item": (1, 0, 1),
    "steal": (-1, 1, -1),
    "observe": (0, 0, 0),
    "buy_item": (0, 0, 0),
    "sell_item": (0, 0, 0),
}


def is_currency_action(action_type: PlayerActionType) -> bool:
    """Return True when action_type uses the currency transfer coordinator.

    Args:
        action_type: Player action type string.

    Returns:
        True for buy_item and sell_item actions.
    """
    return action_type in {"buy_item", "sell_item"}


def has_valid_currency_payload(counterparty_id: str | None, currency_amount: int | None) -> bool:
    """Return True when required currency payload fields are present.

    Args:
        counterparty_id: Optional counterparty character id.
        currency_amount: Optional currency transfer amount.

    Returns:
        True when both fields are non-None.
    """
    return counterparty_id is not None and currency_amount is not None


def resolve_request_id(
    *,
    provided_request_id: str,
    action_type: PlayerActionType,
    player_id: str,
    counterparty_id: str,
) -> str:
    """Resolve request id from header or deterministic fallback format.

    Args:
        provided_request_id: X-Request-ID header value (may be empty).
        action_type: Player action type string.
        player_id: Player character id.
        counterparty_id: Counterparty character id.

    Returns:
        Non-empty request id string.
    """
    candidate = provided_request_id.strip()
    if candidate != "":
        return candidate
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return f"action:{action_type}:{player_id}:{counterparty_id}:{timestamp}"


def resolve_session_scope(session_scope: str | None, player_id: str, npc_id: str) -> str:
    """Resolve session scope for idempotent currency transfer calls.

    Args:
        session_scope: Explicit scope override from the request payload.
        player_id: Player character id.
        npc_id: NPC character id.

    Returns:
        Scope string used to namespace the currency transfer.
    """
    return session_scope or f"{player_id}:{npc_id}"


def resolve_currency_reason(action_type: PlayerActionType, currency_reason: str | None) -> str:
    """Resolve semantic reason for currency transfer provenance.

    Args:
        action_type: Player action type string.
        currency_reason: Explicit reason override from the request payload.

    Returns:
        Non-empty reason string used for delta log provenance.
    """
    return currency_reason or f"action:{action_type}"


def relation_deltas_for_action(action_type: PlayerActionType, intensity: int) -> dict[str, int]:
    """Compute bounded relation deltas from action type and intensity.

    Args:
        action_type: Player action type string.
        intensity: Raw intensity value (0–100) from the game engine.

    Returns:
        Dict with trust, fear, and affection delta values clamped to MAX_ACTION_DELTA.
    """
    raw_delta = intensity // 10
    delta = min(MAX_ACTION_DELTA, max(-MAX_ACTION_DELTA, raw_delta))
    trust_m, fear_m, affection_m = _ACTION_DELTA_MULTIPLIERS.get(action_type, (0, 0, 0))
    return {
        "trust": trust_m * delta,
        "fear": fear_m * delta,
        "affection": affection_m * delta,
    }
