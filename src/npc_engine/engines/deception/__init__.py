"""
Package: deception
Layer: engines
Purpose: Engine for planting deliberate false beliefs on NPCs (EXP-228 / DEC-103).
Does NOT: call LLMs, execute Cypher directly, or validate world-state consistency.
Dependencies injected: none (re-export package).
Public surface: DeceptionEngine, DeceptionBelief
"""

from __future__ import annotations

from npc_engine.engines.deception.deception_engine import DeceptionBelief, DeceptionEngine

__all__ = [
    "DeceptionEngine",
    "DeceptionBelief",
]
