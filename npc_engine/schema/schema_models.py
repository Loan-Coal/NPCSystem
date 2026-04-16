"""
schema_models.py - Pydantic models for game_schema.yaml meta-schema.

Does NOT: load files from disk.

Dependencies injected: None.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FieldType = Literal["str", "int", "float", "bool"]
SemanticTag = Literal["context_tier_0", "context_tier_a", "gossip_weight"]


class ExtensionField(BaseModel):
    """Schema definition for one extension field."""

    type: FieldType
    range: list[int | float] | None = None
    default: str | int | float | bool | None = None
    description: str = ""
    semantics: list[SemanticTag] = Field(default_factory=list)
    indexed: bool = False

    model_config = ConfigDict(frozen=True)


class CoreTypeConfig(BaseModel):
    """Extension field config for a core node type."""

    extension_fields: dict[str, ExtensionField] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class EnumExtensions(BaseModel):
    """Schema enum extension values for known enum families."""

    event_type: list[str] = Field(default_factory=list)
    participation_role: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class SchemaConfig(BaseModel):
    """Root schema model for game_schema.yaml."""

    schema_version: str
    core_types: dict[str, CoreTypeConfig] = Field(default_factory=dict)
    enum_extensions: EnumExtensions = Field(default_factory=EnumExtensions)

    model_config = ConfigDict(frozen=True)
