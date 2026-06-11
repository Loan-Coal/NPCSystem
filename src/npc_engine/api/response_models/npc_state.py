"""
Module: npc_state (response_models)
Layer: api
Purpose: Typed sub-models for NPCStateResponse so its OpenAPI schema describes the
         character / relations / events payloads instead of opaque `dict`.
Does NOT: perform graph I/O, validation business logic, or LLM calls.
Dependencies: pydantic.
Dependencies injected: None.
Used by: api.schemas.NPCStateResponse, api.routes.npc_state.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CharacterNode(BaseModel):
    """Character node properties.

    Carries the stable `id` plus registry-dynamic fields (name, archetype,
    faction, ...). `extra="allow"` keeps the model schema-useful without coupling
    it to the dynamic node registry, and preserves the original wire shape.
    """

    model_config = ConfigDict(extra="allow")

    id: str


class RelationEdge(BaseModel):
    """One outgoing RELATES_TO relation paired with its target character."""

    model_config = ConfigDict(extra="allow")

    relation: dict[str, Any] = Field(default_factory=dict)
    character: CharacterNode


class EventNode(BaseModel):
    """One KNOWS_ABOUT event entry for an NPC (event props + knowledge framing)."""

    model_config = ConfigDict(extra="allow")

    event: dict[str, Any] = Field(default_factory=dict)
    knowledge_state: str | None = None
    distorted_summary: str | None = None
