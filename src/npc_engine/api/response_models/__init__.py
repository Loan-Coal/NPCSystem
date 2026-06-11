"""
Package: response_models
Layer: api
Purpose: Typed Pydantic response sub-models used as route `response_model` so the
         generated OpenAPI schema emits real bodies instead of empty `{}`.
Does NOT: perform graph I/O, validation business logic, or LLM calls.
Dependencies injected: None.
Public surface: CharacterNode, RelationEdge, EventNode (from .npc_state).
"""

from __future__ import annotations

from npc_engine.api.response_models.npc_state import CharacterNode, EventNode, RelationEdge

__all__ = ["CharacterNode", "EventNode", "RelationEdge"]
