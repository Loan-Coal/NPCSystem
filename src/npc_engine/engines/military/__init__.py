"""
Package: military
Layer: engines
Purpose: Military engine stub for Phase 7.4 Strategy/4X — no-op tick placeholder.
Does NOT: perform combat resolution, resource yield, or LLM calls (see ISSUES.md ISSUE-001).
Dependencies injected: None (engines are constructed in dependency_singletons).
Public surface: MilitaryEngine
"""

from npc_engine.engines.military.military_engine import MilitaryEngine

__all__ = ["MilitaryEngine"]
