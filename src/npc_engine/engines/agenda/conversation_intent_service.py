"""
Module: conversation_intent_service
Layer: engines
Purpose: Score whether an NPC wants to open dialogue with a co-located player.
         Returns ConversationIntent Pydantic models for need, event, and goal triggers.
Does NOT: persist intents, call LLMs, open transactions, or hold a Neo4j session.
Dependencies: engines.ports.intent_port (injected), common.intent_models, config
Dependencies injected: IntentGraphPort (first positional arg; trigger reads).
Used by: engines.agenda.intent_formation_engine
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from npc_engine.common.intent_models import ConversationIntent
from npc_engine.config import get_settings

if TYPE_CHECKING:
    from npc_engine.engines.ports.intent_port import IntentGraphPort

_logger = logging.getLogger(__name__)

# One intent per trigger category maximum per (npc, player, tick) call.
_MAX_INTENTS_PER_CALL: int = 3


async def score_intents(
    intent_repo: IntentGraphPort,
    npc_id: str,
    player_id: str,
    tick: int,
) -> list[ConversationIntent]:
    """Score all intent candidates for one NPC/player pair at the given tick.

    Co-location is checked first; different locations return [] immediately.
    Otherwise scores up to one intent per trigger category and returns those
    whose score >= config.MIN_INTENT_SCORE.

    Args:
        intent_repo: Intent graph port providing the trigger reads.
        npc_id: ID of the NPC being evaluated.
        player_id: ID of the potentially co-located player.
        tick: Current game tick.

    Returns:
        List of ConversationIntent (at most _MAX_INTENTS_PER_CALL = 3 entries).
    """
    npc_loc = await intent_repo.get_npc_location(npc_id=npc_id)
    player_loc = await intent_repo.get_player_location(player_id=player_id)
    if npc_loc is None or player_loc is None or npc_loc != player_loc:
        return []

    settings = get_settings()
    threshold = settings.MIN_INTENT_SCORE
    expiry_ticks = settings.INTENT_EXPIRY_TICKS
    intents: list[ConversationIntent] = []

    await _score_need(intent_repo, npc_id, player_id, tick, threshold, intents)
    await _score_event(intent_repo, npc_id, player_id, tick, threshold, expiry_ticks, intents)
    await _score_goal(intent_repo, npc_id, player_id, tick, threshold, intents)

    _logger.debug(
        "intent_scoring_done",
        extra={"npc_id": npc_id, "player_id": player_id, "tick": tick, "count": len(intents)},
    )
    return intents


async def _score_need(
    intent_repo: IntentGraphPort,
    npc_id: str,
    player_id: str,
    tick: int,
    threshold: float,
    intents: list[ConversationIntent],
) -> None:
    needs = await intent_repo.get_unmet_needs(npc_id=npc_id)
    if not needs:
        return
    best = max(needs, key=lambda n: (100 - int(n["level"])) / 100.0)
    score = (100 - int(best["level"])) / 100.0
    if score >= threshold:
        intents.append(ConversationIntent(
            npc_id=npc_id,
            player_id=player_id,
            tick=tick,
            score=score,
            reason=f"I need help with {best['kind']}",
            trigger_type="need",
            trigger_ref=str(best["id"]),
        ))


async def _score_event(
    intent_repo: IntentGraphPort,
    npc_id: str,
    player_id: str,
    tick: int,
    threshold: float,
    expiry_ticks: int,
    intents: list[ConversationIntent],
) -> None:
    since_tick = max(0, tick - expiry_ticks)
    events = await intent_repo.get_witnessed_events(npc_id=npc_id, since_tick=since_tick)
    if not events:
        return
    best = max(events, key=lambda e: int(e["learned_at_tick"]))
    score = max(0.0, 1.0 - (tick - int(best["learned_at_tick"])) / expiry_ticks)
    if score >= threshold:
        summary = str(best.get("summary", ""))[:40]
        intents.append(ConversationIntent(
            npc_id=npc_id,
            player_id=player_id,
            tick=tick,
            score=score,
            reason=f"Did you hear about {summary}",
            trigger_type="event",
            trigger_ref=str(best["id"]),
        ))


async def _score_goal(
    intent_repo: IntentGraphPort,
    npc_id: str,
    player_id: str,
    tick: int,
    threshold: float,
    intents: list[ConversationIntent],
) -> None:
    goals = await intent_repo.get_unresolved_goals(npc_id=npc_id)
    if not goals:
        return
    best = max(goals, key=lambda g: int(g["urgency"]) / 100.0)
    score = int(best["urgency"]) / 100.0
    if score >= threshold:
        desc = str(best.get("description", ""))[:40]
        intents.append(ConversationIntent(
            npc_id=npc_id,
            player_id=player_id,
            tick=tick,
            score=score,
            reason=f"There's something I need to discuss: {desc}",
            trigger_type="goal",
            trigger_ref=str(best["id"]),
        ))
