"""
quest_engine_helpers.py - Private helpers for QuestLifecycleEngine.
Layer: engines
Purpose: Shared utility functions used by quest lifecycle, offer, and reward modules.
Does NOT: expose public lifecycle API, touch HTTP concerns, or open Neo4j sessions.
Dependencies: engines/quest/models, type_registry, utils/errors.
Dependencies injected: None.
Used by: engines/quest/quest_lifecycle_engine, quest_offer_service, quest_reward_router.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from npc_engine.engines.quest.models import QuestRewardItem, QuestTransitionMeta
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.type_registry.node_validator import validate_node_write


def is_trusted_reward_source(reward_source_id: str) -> bool:
    """Return True when the reward source is trusted.

    Trusted sources: the literal ``"system"`` sentinel, or any non-empty
    character ID (NPC purse). Callers that use a character ID must separately
    verify affordability via ``get_character_balance`` before applying rewards.

    Args:
        reward_source_id: Source identifier to validate.

    Returns:
        True when ``reward_source_id`` is ``"system"`` or a non-empty character ID.
    """
    return bool(reward_source_id) and reward_source_id != ""


def normalize_item_rewards(item_rewards: list[QuestRewardItem]) -> list[QuestRewardItem]:
    """Deduplicate and sum item rewards by item_id.

    Args:
        item_rewards: Raw list of item reward entries (may contain duplicates).

    Returns:
        Sorted, deduplicated list with quantities summed per item_id.
    """

    quantity_by_item_id: dict[str, int] = {}
    for reward in item_rewards:
        quantity_by_item_id[reward.item_id] = quantity_by_item_id.get(reward.item_id, 0) + reward.quantity
    return [
        QuestRewardItem(item_id=item_id, quantity=quantity)
        for item_id, quantity in sorted(quantity_by_item_id.items())
    ]


def build_lifecycle_event(
    *,
    registry: TypeRegistry,
    quest_id: str,
    player_id: str,
    event_type: str,
    summary: str,
    meta: QuestTransitionMeta,
) -> Any:
    """Construct a typed lifecycle event node using the registry event model.

    Args:
        registry: Type registry providing the ``event`` node constructor.
        quest_id: Quest identifier; part of the composite event ID.
        player_id: Player identifier; part of the composite event ID.
        event_type: Lifecycle event type string (e.g. ``"quest_offered"``).
        summary: Human-readable event summary.
        meta: Transition metadata for provenance and idempotency fields.

    Returns:
        A typed event node instance from the registry model.
    """

    now = datetime.now(timezone.utc)
    raw_props = {
        "id": f"{quest_id}:{player_id}:{event_type}:{meta.request_id}",
        "summary": summary,
        "severity": 20,
        "location_id": "quest",
        "occurred_at": now.isoformat(),
        "tick_id": int(now.timestamp()),
        "event_type": event_type,
        "is_public": True,
        "producer": "quest_lifecycle_engine",
        "origin_engine": "quest",
        "schema_version": "v1.4",
        "last_graph_updated_at": now.isoformat(),
        "provenance": {
            "request_id": meta.request_id,
            "idempotency_key": meta.idempotency_key,
            "idempotency_request_hash": meta.idempotency_request_hash,
            "actor_id": meta.actor_id,
            "reason": meta.reason,
        },
    }
    validated_props = validate_node_write(registry, "event", raw_props)
    return registry.node_models["event"](**validated_props)


