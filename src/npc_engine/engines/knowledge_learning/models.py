"""
Module: models
Layer: engines
Purpose: Pydantic v2 data models for the knowledge learning engine input/output boundary.
Does NOT: contain engine logic, write to the graph, or call LLMs.
Dependencies: pydantic
Dependencies injected: none.
Used by: engines.knowledge_learning.knowledge_extraction_engine, engines.dialogue.dialogue_handler
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LearnedFact(BaseModel):
    """A single fact the player explicitly stated during a dialogue turn."""

    model_config = ConfigDict(frozen=True)

    content: str = Field(description="Raw text of the player-stated fact.")
    source_character_id: str = Field(description="ID of the character who stated the fact.")


class KnowledgeExtractionResult(BaseModel):
    """Outcome summary returned by KnowledgeExtractionEngine.process."""

    model_config = ConfigDict(frozen=True)

    written: int = Field(default=0, ge=0, description="Number of belief nodes successfully written.")
    skipped: int = Field(default=0, ge=0, description="Number of facts skipped due to validation.")
