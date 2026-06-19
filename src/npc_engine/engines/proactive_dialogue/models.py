"""
Module: models
Layer: engines
Purpose: Pydantic v2 data models for the ProactiveDialogueEngine — trigger input and
         line output crossing module boundaries.
Does NOT: implement trigger logic, LLM calls, or graph queries.
Dependencies: None (pure data models).
Dependencies injected: None.
Used by: engines.proactive_dialogue.proactive_engine, api.routes.dialogue_ws
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ProactiveReason = Literal["unshared_memory", "unmet_need", "pending_rumor", "witnessed_event"]


class ProactiveTrigger(BaseModel):
    """Input trigger passed from check_trigger to generate_line.

    Carries the identity of the NPC/player pair and the qualifying memory
    that caused the trigger to fire.
    """

    npc_id: str = Field(..., description="ID of the NPC initiating the line.")
    player_id: str = Field(..., description="ID of the co-located idle player.")
    tick_id: int = Field(..., description="Game tick at which the trigger was detected.")
    reason: ProactiveReason = Field(..., description="Why the NPC is speaking proactively.")
    memory_id: str = Field(..., description="ID of the qualifying Memory node.")
    memory_content: str = Field(..., description="Text content of the qualifying memory.")
    memory_vividness: int = Field(..., ge=0, le=100, description="Vividness of the memory (0–100).")


class ProactiveLine(BaseModel):
    """Output produced by generate_line; emitted as a WS push message (DEC-073).

    The ``to_ws_message()`` method serialises to the approved wire format.
    """

    npc_id: str = Field(..., description="ID of the NPC speaking.")
    content: str = Field(..., description="In-character line produced by the LLM.")
    reason: ProactiveReason = Field(..., description="Trigger category for the client.")
    tick: int = Field(..., description="Game tick at which the line was generated.")

    def to_ws_message(self) -> dict[str, Any]:
        """Serialise to the DEC-073 approved WebSocket envelope.

        Returns:
            Dict with keys ``type``, ``npc_id``, ``content``, ``reason``, ``tick``.
        """
        return {
            "type": "proactive_line",
            "npc_id": self.npc_id,
            "content": self.content,
            "reason": self.reason,
            "tick": self.tick,
        }
