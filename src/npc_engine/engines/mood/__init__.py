"""
Package: mood
Layer: engines
Purpose: Mood contagion engine — spreads emotional states between co-located NPCs each tick.
Does NOT: expose HTTP routes or manage tick scheduling.
Dependencies: engines.mood.mood_contagion_engine
Dependencies injected: None (engines are constructed in dependency_singletons).
Public surface: MoodContagionEngine
"""

from npc_engine.engines.mood.mood_contagion_engine import MoodContagionEngine

__all__ = ["MoodContagionEngine"]
