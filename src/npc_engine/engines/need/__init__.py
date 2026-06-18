"""
Package: need
Layer: engines
Purpose: Need decay engine for Phase 7.3 Social Simulation — decays character need levels each tick.
Does NOT: expose HTTP routes or manage tick scheduling.
Dependencies injected: None (engines are constructed in dependency_singletons).
Public surface: NeedDecayEngine
"""

from __future__ import annotations

from npc_engine.engines.need.need_decay_engine import NeedDecayEngine

__all__ = ["NeedDecayEngine"]
