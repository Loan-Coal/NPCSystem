"""
Module: intent_queue_reader
Layer: graph
Purpose: Read pending intents from the PendingIntent queue for delivery to clients.
Does NOT: score intents, write to the graph, or call LLMs.
Dependencies: graph.intent_queries, engines.agenda.conversation_intent_service, config
Dependencies injected: AsyncSession (caller-managed).
Used by: api.routes.dialogue (GET /v1/dialogue/pending)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from neo4j import AsyncSession

from npc_engine.common.intent_models import ConversationIntent
from npc_engine.graph.intent_queries import get_pending_for_player

if TYPE_CHECKING:
    from npc_engine.config import Settings

_logger = logging.getLogger(__name__)


async def get_pending_intents(
    session: AsyncSession,
    player_id: str,
    *,
    settings: "Settings",
) -> list["ConversationIntent"]:
    """Return pending intents for a player ordered by score DESC.

    Fetches up to MAX_PENDING_INTENTS_PER_PLAYER pending PendingIntent nodes
    for player_id. Results are returned as ConversationIntent instances so the
    API layer can convert them to the public response schema without touching
    raw dicts.

    Args:
        session: Active Neo4j async session.
        player_id: Player character id to fetch intents for.
        settings: Application settings for the per-player cap.

    Returns:
        List of ConversationIntent ordered by score descending.
    """
    rows = await get_pending_for_player(
        session, player_id, limit=settings.MAX_PENDING_INTENTS_PER_PLAYER
    )
    intents = []
    for row in rows:
        intents.append(ConversationIntent(
            npc_id=str(row["npc_id"]),
            player_id=str(row["player_id"]),
            tick=int(row["tick"]),
            score=float(row["score"]),
            reason=str(row["reason"]),
            trigger_type=row["trigger_type"],
            trigger_ref=str(row["trigger_ref"]),
        ))
    _logger.debug(
        "intent_queue_read",
        extra={"player_id": player_id, "count": len(intents)},
    )
    return intents
