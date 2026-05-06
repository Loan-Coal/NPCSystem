"""
quest_engine_helpers.py - Private helpers for QuestLifecycleEngine.

Does NOT: expose public lifecycle API or touch HTTP concerns.

Dependencies injected: TypeRegistry, AsyncSession.
"""

from __future__ import annotations

from datetime import datetime, timezone

from neo4j import AsyncSession

from npc_engine.engines.quest.models import QuestRewardItem, QuestTransitionMeta
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.utils.errors import QuestTransitionError


def is_trusted_reward_source(reward_source_id: str) -> bool:
    """Return True if the reward source ID is a trusted system source.

    Args:
        reward_source_id: Source identifier to validate.

    Returns:
        True when ``reward_source_id`` equals ``"system"``.
    """

    return reward_source_id == "system"


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


def ensure_transaction_session(session: AsyncSession) -> None:
    """Raise QuestTransitionError when the session does not support transactions.

    Args:
        session: Neo4j async session to validate.

    Raises:
        QuestTransitionError: If ``session`` lacks a ``begin_transaction`` attribute.
    """

    if not hasattr(session, "begin_transaction"):
        raise QuestTransitionError(
            code="QUEST_EVENT_SESSION_INVALID",
            detail="Quest lifecycle event emission requires a transaction-capable session",
        )


def build_lifecycle_event(
    *,
    registry: TypeRegistry,
    quest_id: str,
    player_id: str,
    event_type: str,
    summary: str,
    meta: QuestTransitionMeta,
) -> object:
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
    event_model = registry.node_models["event"]
    return event_model(
        id=f"{quest_id}:{player_id}:{event_type}:{meta.request_id}",
        summary=summary,
        severity=20,
        location_id="quest",
        occurred_at=now.isoformat(),
        tick_id=int(now.timestamp()),
        event_type=event_type,
        is_public=True,
        producer="quest_lifecycle_engine",
        origin_engine="quest",
        schema_version="v1.4",
        last_graph_updated_at=now.isoformat(),
        provenance={
            "request_id": meta.request_id,
            "idempotency_key": meta.idempotency_key,
            "idempotency_request_hash": meta.idempotency_request_hash,
            "actor_id": meta.actor_id,
            "reason": meta.reason,
        },
    )


