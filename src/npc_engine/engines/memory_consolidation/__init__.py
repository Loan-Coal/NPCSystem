"""
Package: memory_consolidation
Layer: engines
Purpose: Consolidates NPC session turn histories into long-term Memory nodes via LLM summarisation.
Does NOT: implement LLM adapters or Neo4j queries directly.
Dependencies: engines.memory_consolidation.memory_consolidation_engine
Dependencies injected: None (re-export package).
Public surface: MemoryConsolidationEngine
"""

from __future__ import annotations

from npc_engine.engines.memory_consolidation.memory_consolidation_engine import (
    MemoryConsolidationEngine,
)

__all__ = ["MemoryConsolidationEngine"]
