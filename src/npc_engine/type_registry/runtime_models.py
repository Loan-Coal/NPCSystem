"""
runtime_models.py - Builds dynamic Pydantic node and edge models from registry contracts.
Layer: config
Purpose: (auto-detected — review)

Does NOT: persist graph data or perform request validation.

Dependencies injected: TypeRegistry.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model

from npc_engine.type_registry.contracts import RuntimeFieldDefinition, TypeRegistry


TYPE_MAP: dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}


class _FrozenBase(BaseModel):
    """Frozen, no-extra base used by all dynamic runtime models."""

    model_config = ConfigDict(frozen=True, extra="forbid")


@dataclass(frozen=True)
class RuntimeModelBundle:
    """Immutable bundle of dynamic node and edge model classes."""

    node_models: Mapping[str, type[BaseModel]]
    edge_models: Mapping[str, type[BaseModel]]


def build_runtime_models(*, registry: TypeRegistry) -> RuntimeModelBundle:
    """Build dynamic runtime models for all base and custom node and edge types.

    Args:
        registry: Fully merged immutable type registry.

    Returns:
        Bundle of dynamically created Pydantic model classes keyed by type name.
    """

    node_models = _build_node_models(registry=registry)
    edge_models = _build_edge_models(registry=registry)
    return RuntimeModelBundle(
        node_models=MappingProxyType(node_models),
        edge_models=MappingProxyType(edge_models),
    )


def _build_node_models(*, registry: TypeRegistry) -> dict[str, type[BaseModel]]:
    models: dict[str, type[BaseModel]] = {}
    node_names = {
        *registry.base_node_types.keys(),
        *registry.core_types.keys(),
        *registry.custom_node_types.keys(),
    }
    for node_name in sorted(node_names):
        fields = _merged_node_fields(registry=registry, node_name=node_name)
        model_name = f"{_to_pascal_case(node_name)}Node"
        model = create_model(model_name, __base__=_FrozenBase, **_build_model_fields(fields=fields))
        models[node_name.lower()] = model
        models[node_name] = model
    return models


def _build_edge_models(*, registry: TypeRegistry) -> dict[str, type[BaseModel]]:
    models: dict[str, type[BaseModel]] = {}
    edge_names = {
        *registry.base_edge_types.keys(),
        *registry.custom_edge_types.keys(),
    }
    for edge_name in sorted(edge_names):
        edge_definition = registry.base_edge_types.get(edge_name)
        if edge_definition is None:
            edge_definition = registry.custom_edge_types[edge_name]
        model_name = f"{_to_pascal_case(edge_name)}Edge"
        model = create_model(model_name, __base__=_FrozenBase, **_build_model_fields(fields=edge_definition.fields))
        models[edge_name.lower()] = model
        models[edge_name] = model
    return models


def _merged_node_fields(*, registry: TypeRegistry, node_name: str) -> Mapping[str, RuntimeFieldDefinition]:
    fields: dict[str, RuntimeFieldDefinition] = {}
    lower_name = node_name.lower()
    fields.update(registry.base_node_types.get(lower_name, {}))
    fields.update(registry.core_types.get(lower_name, {}))
    fields.update(registry.custom_node_types.get(node_name, {}))
    fields.update(registry.custom_node_types.get(lower_name, {}))
    return fields


def _build_model_fields(*, fields: Mapping[str, RuntimeFieldDefinition]) -> dict[str, Any]:
    model_fields: dict[str, Any] = {}
    for field_name, definition in fields.items():
        annotation = _annotation_for(definition)
        field_info = _field_info_for(definition=definition)
        model_fields[field_name] = (annotation, field_info)
    return model_fields


def _annotation_for(definition: RuntimeFieldDefinition) -> Any:
    if definition.field_type == "list":
        item_type = TYPE_MAP.get(definition.list_item_type or "str", Any)
        return list[item_type]  # type: ignore[valid-type]
    if definition.field_type == "dict":
        value_type = TYPE_MAP.get(definition.dict_value_type or "str", Any)
        return dict[str, value_type]  # type: ignore[valid-type]
    return TYPE_MAP[definition.field_type]


def _field_info_for(*, definition: RuntimeFieldDefinition) -> Any:
    field_kwargs: dict[str, Any] = {}
    if definition.description:
        field_kwargs["description"] = definition.description
    if definition.range_limits is not None and definition.field_type in {"int", "float"}:
        lower, upper = definition.range_limits
        field_kwargs["ge"] = lower
        field_kwargs["le"] = upper

    if definition.default is not None:
        return Field(default=definition.default, **field_kwargs)
    if definition.required:
        return Field(..., **field_kwargs)
    if definition.field_type == "list":
        return Field(default_factory=list, **field_kwargs)
    if definition.field_type == "dict":
        return Field(default_factory=dict, **field_kwargs)
    return Field(default=None, **field_kwargs)


def _to_pascal_case(value: str) -> str:
    parts = [part for part in value.replace("-", "_").split("_") if part]
    return "".join(part[:1].upper() + part[1:].lower() for part in parts) or value[:1].upper() + value[1:]