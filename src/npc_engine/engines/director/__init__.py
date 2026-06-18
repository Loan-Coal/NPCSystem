"""
Package: director
Layer: engines
Purpose: Drama director engine — observes engagement signals and decides whether to
         inject a story beat to re-engage the player. Slice 2 (F1.5) adds DirectorTick,
         the scheduler adapter that gates the events engine on the director's signal.
Does NOT: call the LLM or write graph nodes at the package level; submodules own I/O.
Dependencies injected: None at package level; see submodules.
Public surface: DirectorDecision, decide, IDLE_INJECT_THRESHOLD_TICKS, BEAT_KINDS,
                DirectorTick
"""

from __future__ import annotations

from npc_engine.engines.director.director_engine import (
    DirectorDecision,
    decide,
    IDLE_INJECT_THRESHOLD_TICKS,
    BEAT_KINDS,
)
from npc_engine.engines.director.director_tick import DirectorTick

__all__ = [
    "DirectorDecision",
    "decide",
    "IDLE_INJECT_THRESHOLD_TICKS",
    "BEAT_KINDS",
    "DirectorTick",
]
