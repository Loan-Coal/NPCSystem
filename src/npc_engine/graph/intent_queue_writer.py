"""
Module: intent_queue_writer
Layer: graph
Purpose: Write operations for the PendingIntent queue — enqueue, mark delivered,
         and expire stale intents. Enforces per-NPC queue cap.
Does NOT: score intents, read for delivery, or call LLMs.
Dependencies: graph.intent_queries, engines.agenda.conversation_intent_service, config
Dependencies injected: AsyncSession (caller-managed).
Used by: engines.agenda.intent_formation_engine, api.routes.dialogue
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from neo4j import AsyncSession

from npc_engine.common.intent_models import ConversationIntent
from npc_engine.graph.intent_queries import (
    count_npc_pending_intents,
    delete_intent_by_id,
    expire_stale_intents,
    get_lowest_score_pending,
    mark_intent_delivered,
    merge_pending_intent,
)

if TYPE_CHECKING:
    from npc_engine.config import Settings

_logger = logging.getLogger(__name__)


async def enqueue_intent(
    session: AsyncSession,
    intent: "ConversationIntent",
    *,
    settings: "Settings",
) -> None:
    """Enqueue a ConversationIntent as a PendingIntent node.

    Enforces per-NPC cap: if the NPC already has >= MAX_PENDING_INTENTS_PER_NPC
    pending intents, the lowest-score one is deleted before the new one is merged.
    MERGE on a deterministic id prevents duplicate enqueues for the same
    (npc_id, player_id, tick, trigger_type) combination.

    Args:
        session: Active Neo4j async session.
        intent: Scored intent to persist.
        settings: Application settings for cap values.
    """
    intent_id = f"{intent.npc_id}:{intent.player_id}:{intent.tick}:{intent.trigger_type}"

    count = await count_npc_pending_intents(session, intent.npc_id)
    if count >= settings.MAX_PENDING_INTENTS_PER_NPC:
        lowest = await get_lowest_score_pending(session, intent.npc_id)
        if lowest is not None and float(lowest["score"]) < intent.score:
            await delete_intent_by_id(session, lowest["id"])
            _logger.debug(
                "intent_cap_evict",
                extra={"npc_id": intent.npc_id, "evicted_id": lowest["id"]},
            )
        elif lowest is not None:
            _logger.debug(
                "intent_cap_drop",
                extra={"npc_id": intent.npc_id, "dropped_score": intent.score},
            )
            return

    await merge_pending_intent(
        session,
        id=intent_id,
        npc_id=intent.npc_id,
        player_id=intent.player_id,
        tick=intent.tick,
        score=intent.score,
        reason=intent.reason,
        trigger_type=intent.trigger_type,
        trigger_ref=intent.trigger_ref,
        created_tick=intent.tick,
    )


async def mark_delivered(session: AsyncSession, intent_id: str) -> None:
    """Set status='delivered' on the PendingIntent with the given id.

    Args:
        session: Active Neo4j async session.
        intent_id: Unique intent id returned from get_pending_intents.
    """
    await mark_intent_delivered(session, intent_id)


async def expire_old_intents(session: AsyncSession, *, cutoff_tick: int) -> int:
    """Expire pending intents whose created_tick is below cutoff_tick.

    Args:
        session: Active Neo4j async session.
        cutoff_tick: Intents with created_tick < cutoff_tick are marked expired.

    Returns:
        Count of intents now marked expired.
    """
    return await expire_stale_intents(session, cutoff_tick=cutoff_tick)
