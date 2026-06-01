"""
contracts.py - Type-registry document contracts and immutable runtime models.

Does NOT: read extension files from disk or apply merge policies.

Dependencies injected: None.
"""

from dataclasses import dataclass, field
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from npc_engine.schema.schema_models import CoreTypeConfig, CustomEdgeTypeConfig, CustomNodeTypeConfig, EnumExtensions


FieldType = Literal["str", "int", "float", "bool"]
CollectionValueType = Literal["str", "int", "float", "bool"]


class RegistryExtensionDocument(BaseModel):
    """One extension YAML document loaded at startup."""

    core_types: dict[str, CoreTypeConfig] = Field(default_factory=dict)
    custom_node_types: dict[str, CustomNodeTypeConfig] = Field(default_factory=dict)
    custom_edge_types: dict[str, CustomEdgeTypeConfig] = Field(default_factory=dict)
    enum_extensions: EnumExtensions = Field(default_factory=EnumExtensions)

    model_config = ConfigDict(frozen=True, extra="forbid")


@dataclass(frozen=True)
class RuntimeFieldDefinition:
    """Immutable runtime field contract used by the registry."""

    field_type: str
    required: bool
    range_limits: tuple[int | float, int | float] | None
    default: str | int | float | bool | None
    description: str
    semantics: tuple[str, ...]
    indexed: bool
    max_bytes: int = 512
    list_item_type: CollectionValueType | None = None
    dict_value_type: CollectionValueType | None = None


@dataclass(frozen=True)
class RuntimeEdgeTypeDefinition:
    """Immutable runtime edge contract including endpoint topology.

    src_type may be a single type string or a tuple of type strings when the
    edge accepts multiple source node types (e.g. ('location', 'item') for
    SATISFIES_NEED).
    """

    src_type: str | tuple[str, ...]
    dst_type: str
    directional: bool
    cascade_on_delete: tuple[str, ...]
    fields: Mapping[str, RuntimeFieldDefinition]


@dataclass(frozen=True)
class TypeRegistry:
    """Immutable graph type registry shared across request handling."""

    schema_version: str
    base_node_types: Mapping[str, Mapping[str, RuntimeFieldDefinition]] = field(default_factory=dict)
    base_edge_types: Mapping[str, RuntimeEdgeTypeDefinition] = field(default_factory=dict)
    core_types: Mapping[str, Mapping[str, RuntimeFieldDefinition]] = field(default_factory=dict)
    custom_node_types: Mapping[str, Mapping[str, RuntimeFieldDefinition]] = field(default_factory=dict)
    custom_edge_types: Mapping[str, RuntimeEdgeTypeDefinition] = field(default_factory=dict)
    enum_extensions: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    node_models: Mapping[str, type[BaseModel]] = field(default_factory=dict)
    edge_models: Mapping[str, type[BaseModel]] = field(default_factory=dict)
