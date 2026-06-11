"""
Package: scheming
Layer: engines
Purpose: Long-horizon covert scheming engine — forms capped scheme nodes and
         advances scheme steps via the graph layer. Detection/investigation deferred
         to slice 2.
Does NOT: call LLMs, contain Cypher queries, wire into the scheduler, or import
          from the investigation engine (graveyard).
Dependencies injected: Settings (via SchemingEngine constructor).
Public surface: SchemingEngine, SchemeInput, SchemeStepInput
"""

from npc_engine.engines.scheming.scheming_engine import (
    SchemeInput,
    SchemeStepInput,
    SchemingEngine,
)

__all__ = ["SchemingEngine", "SchemeInput", "SchemeStepInput"]
