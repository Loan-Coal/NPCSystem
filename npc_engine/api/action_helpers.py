"""
action_helpers.py - Pure helpers for /action route branching and payload shaping.

Does NOT: execute graph writes.

Dependencies injected: None.
"""

from datetime import datetime, timezone

from api.schemas import PlayerActionType


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
    """Return True when action_type uses the currency transfer coordinator."""

    return action_type in {"buy_item", "sell_item"}


def has_valid_currency_payload(counterparty_id: str | None, currency_amount: int | None) -> bool:
    """Return True when required currency payload fields are present."""

    return counterparty_id is not None and currency_amount is not None


def resolve_request_id(
    *,
    provided_request_id: str,
    action_type: PlayerActionType,
    player_id: str,
    counterparty_id: str,
) -> str:
    """Resolve request id from header or deterministic fallback format."""

    candidate = provided_request_id.strip()
    if candidate != "":
        return candidate
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return f"action:{action_type}:{player_id}:{counterparty_id}:{timestamp}"


def resolve_session_scope(session_scope: str | None, player_id: str, npc_id: str) -> str:
    """Resolve session scope for idempotent currency transfer calls."""

    return session_scope or f"{player_id}:{npc_id}"


def resolve_currency_reason(action_type: PlayerActionType, currency_reason: str | None) -> str:
    """Resolve semantic reason for currency transfer provenance."""

    return currency_reason or f"action:{action_type}"


def relation_deltas_for_action(action_type: PlayerActionType, intensity: int) -> dict[str, int]:
    """Compute bounded relation deltas from action type and intensity."""

    raw_delta = intensity // 10
    delta = min(MAX_ACTION_DELTA, max(-MAX_ACTION_DELTA, raw_delta))
    trust_m, fear_m, affection_m = _ACTION_DELTA_MULTIPLIERS.get(action_type, (0, 0, 0))
    return {
        "trust": trust_m * delta,
        "fear": fear_m * delta,
        "affection": affection_m * delta,
    }
