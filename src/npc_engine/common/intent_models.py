"""
Module: intent_models
Layer: common
Purpose: Pydantic v2 data model for ConversationIntent — the internal intent object
         produced by the scoring service and consumed by the queue writer/reader.
Does NOT: implement scoring logic, graph queries, or LLM calls.
Dependencies: pydantic (third-party)
Dependencies injected: None (pure data model, no constructor).
Used by: engines.agenda.conversation_intent_service,
         graph.intent_queue_writer, graph.intent_queue_reader
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TriggerType = Literal["need", "event", "goal"]


class ConversationIntent(BaseModel):
    """Intent for an NPC to open dialogue with a co-located player.

    All fields are required; no raw dict crosses module boundaries.
    Produced by engines.agenda.conversation_intent_service.score_intents and
    consumed by graph.intent_queue_writer.enqueue_intent.
    """

    npc_id: str = Field(..., description="ID of the NPC that wants to speak.")
    player_id: str = Field(..., description="ID of the target player.")
    tick: int = Field(..., description="Game tick at which the intent was scored.")
    score: float = Field(..., ge=0.0, le=1.0, description="Intent urgency score (0–1).")
    reason: str = Field(..., description="Human-readable trigger phrase for the client.")
    trigger_type: TriggerType = Field(..., description="Category: need, event, or goal.")
    trigger_ref: str = Field(..., description="ID of the triggering Need, Event, or Goal node.")
