"""
Package: proactive_dialogue
Layer: engines
Purpose: NPC-initiated proactive dialogue: detects high-vividness unshared memories
         co-located with idle players and generates one in-character line via LLM.
Does NOT: wire into the scheduler (slice 2), send WS messages, or persist state.
Dependencies injected: LLMClientProtocol, MemoryServiceProtocol, LocationServiceProtocol.
Public surface: ProactiveDialogueEngine, ProactiveTrigger, ProactiveLine,
                HIGH_VIVIDNESS_THRESHOLD, MIN_IDLE_TICKS
"""

from __future__ import annotations

from npc_engine.engines.proactive_dialogue.models import ProactiveLine, ProactiveTrigger
from npc_engine.engines.proactive_dialogue.proactive_engine import (
    HIGH_VIVIDNESS_THRESHOLD,
    MIN_IDLE_TICKS,
    ProactiveDialogueEngine,
)

__all__ = [
    "ProactiveDialogueEngine",
    "ProactiveTrigger",
    "ProactiveLine",
    "HIGH_VIVIDNESS_THRESHOLD",
    "MIN_IDLE_TICKS",
]
