"""
Package: scheming
Layer: engines
Purpose: Pydantic input/output models for the scheming domain; live tick work is in
         scheme_advance_tick and scheme_detection_tick.
Does NOT: call LLMs, contain Cypher queries, wire into the scheduler, or import
          from the investigation engine (graveyard).
Dependencies injected: none (models only).
Public surface: SchemeInput, SchemeStepInput
"""

from __future__ import annotations

from npc_engine.engines.scheming.scheming_engine import (
    SchemeInput,
    SchemeStepInput,
)

__all__ = ["SchemeInput", "SchemeStepInput"]
