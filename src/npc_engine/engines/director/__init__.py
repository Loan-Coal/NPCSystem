"""
Package: director
Layer: engines
Purpose: Drama director engine — observes engagement signals and decides whether to
         inject a story beat to re-engage the player.
Does NOT: call the graph, call the LLM, or wire into the scheduler (slice 1 only).
Dependencies injected: None at package level; see submodules.
Public surface: DirectorDecision, decide, IDLE_INJECT_THRESHOLD_TICKS, BEAT_KINDS
"""

from npc_engine.engines.director.director_engine import (
    DirectorDecision,
    decide,
    IDLE_INJECT_THRESHOLD_TICKS,
    BEAT_KINDS,
)

__all__ = [
    "DirectorDecision",
    "decide",
    "IDLE_INJECT_THRESHOLD_TICKS",
    "BEAT_KINDS",
]
