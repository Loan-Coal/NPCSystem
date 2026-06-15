"""
Package: military
Layer: engines
Purpose: Per-tick military simulation — battle resolution between opposing armies
         and resource yield for controlling factions (implemented S6.5, ISSUE-031).
Does NOT: call LLMs or perform graph writes directly (delegated to military services).
Dependencies injected: None (engines are constructed in dependency_singletons).
Public surface: MilitaryEngine
"""

from __future__ import annotations

from npc_engine.engines.military.military_engine import MilitaryEngine

__all__ = ["MilitaryEngine"]
