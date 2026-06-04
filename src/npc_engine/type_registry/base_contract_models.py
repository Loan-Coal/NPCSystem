"""
base_contract_models.py - Pydantic contracts for package-internal base type YAML files.
Layer: config
Purpose: (auto-detected — review)

Does NOT: load files from disk.

Dependencies injected: None.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PrimitiveFieldType = Literal["str", "int", "float", "bool"]
CollectionFieldType = Literal["list", "dict"]
BaseFieldType = PrimitiveFieldType | CollectionFieldType
CollectionValueType = Literal["str", "int", "float", "bool"]


class BaseFieldConfig(BaseModel):
    """Field definition for package-internal base node/edge contracts."""

    type: BaseFieldType
    items_type: CollectionValueType | None = None
    values_type: CollectionValueType | None = None
    required: bool = False
    range: list[int | float] | None = None
    default: str | int | float | bool | None = None
    description: str = ""
    indexed: bool = False
    max_bytes: int = 512

    model_config = ConfigDict(frozen=True, extra="forbid")


class BaseNodeTypeDocument(BaseModel):
    """One package-internal base node contract document."""

    node_type: str
    fields: dict[str, BaseFieldConfig] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid")


class BaseEdgeTypeDocument(BaseModel):
    """One package-internal base edge contract document."""

    edge_type: str
    src_type: str | list[str]
    dst_type: str
    directional: bool = True
    cascade_on_delete: list[str] = Field(default_factory=list)
    fields: dict[str, BaseFieldConfig] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid")
