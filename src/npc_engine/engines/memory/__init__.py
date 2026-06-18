"""
Package: memory
Layer: engines
Purpose: High-arousal memory formation and daily vividness decay engine.
Does NOT: persist state directly — delegates all I/O to graph.memory_service.
Dependencies injected: None (MemoryEngine is constructed without arguments).
Public surface: MemoryEngine
"""

from __future__ import annotations

from npc_engine.engines.memory.memory_engine import MemoryEngine

__all__ = ["MemoryEngine"]
