"""
Module: slot_models
Layer: engines
Purpose: Frozen dataclasses for quest slot definitions, fills, and generation results.
Does NOT: validate fills against the graph or call LLMs.
Dependencies: None.
Dependencies injected: None.
Used by: npc_engine.engines.quest_generation.slot_validator,
         npc_engine.engines.quest_generation.quest_generation_engine,
         npc_engine.engines.quest_generation.template_loader
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlotDefinition:
    """Declares one slot in a quest template."""

    name: str
    node_type: str
    required: bool


@dataclass(frozen=True)
class SlotFill:
    """A validated fill for a single slot."""

    slot_name: str
    node_id: str
    node_type: str


@dataclass(frozen=True)
class QuestTemplateRecord:
    """A parsed quest template loaded from a YAML file."""

    id: str
    name: str
    archetype: str
    severity: int
    slot_definitions: tuple[SlotDefinition, ...]
    description_template: str
    reward_template: str


@dataclass(frozen=True)
class GeneratedQuest:
    """The result of a successful quest generation cycle."""

    quest_id: str
    template_id: str
    fills: tuple[SlotFill, ...]
    description: str
