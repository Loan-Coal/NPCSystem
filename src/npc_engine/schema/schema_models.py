"""
schema_models.py - Pydantic models for game_schema.yaml meta-schema.
Layer: config
Purpose: (auto-detected — review)

Does NOT: load files from disk.

Dependencies injected: None.
"""
from __future__ import annotations

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
    max_bytes: int = 512

    model_config = ConfigDict(frozen=True, extra="forbid")


class CoreTypeConfig(BaseModel):
    """Extension field config for a core node type."""

    extension_fields: dict[str, ExtensionField] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid")


class CustomFieldConfig(BaseModel):
    """Schema definition for one custom node/edge field."""

    type: FieldType
    required: bool = False
    range: list[int | float] | None = None
    default: str | int | float | bool | None = None
    description: str = ""
    indexed: bool = False
    max_bytes: int = 512

    model_config = ConfigDict(frozen=True, extra="forbid")


class CustomNodeTypeConfig(BaseModel):
    """Schema definition for one custom node type."""

    fields: dict[str, CustomFieldConfig] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid")


class CustomEdgeTypeConfig(BaseModel):
    """Schema definition for one custom edge type."""

    src_type: str
    dst_type: str
    directional: bool = True
    cascade_on_delete: list[str] = Field(default_factory=list)
    fields: dict[str, CustomFieldConfig] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid")


class EnumExtensions(BaseModel):
    """Schema enum extension values for known enum families."""

    event_type: list[str] = Field(default_factory=list)
    participation_role: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True, extra="forbid")


class SchemaConfig(BaseModel):
    """Root schema model for game_schema.yaml."""

    schema_version: str
    core_types: dict[str, CoreTypeConfig] = Field(default_factory=dict)
    custom_node_types: dict[str, CustomNodeTypeConfig] = Field(default_factory=dict)
    custom_edge_types: dict[str, CustomEdgeTypeConfig] = Field(default_factory=dict)
    enum_extensions: EnumExtensions = Field(default_factory=EnumExtensions)

    model_config = ConfigDict(frozen=True, extra="forbid")
