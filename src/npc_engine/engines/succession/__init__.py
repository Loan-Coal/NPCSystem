"""
Package: succession
Layer: engines
Purpose: Political succession engine for Phase 7.2 — grants vacant titles to eligible heirs.
Does NOT: expose HTTP routes or manage tick scheduling.
Dependencies injected: None (engines are constructed in dependency_singletons).
Public surface: SuccessionEngine
"""

from __future__ import annotations

from npc_engine.engines.succession.succession_engine import SuccessionEngine

__all__ = ["SuccessionEngine"]
