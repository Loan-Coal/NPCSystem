"""
base_contract_loader.py - Loads package-internal base node/edge type contracts.
Layer: config
Purpose: Loads package-internal base node/edge type contracts.

Does NOT: load external extension contracts.

Dependencies injected: None.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import MappingProxyType

import yaml
from pydantic import ValidationError

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.type_registry.base_contract_models import BaseEdgeTypeDocument, BaseFieldConfig, BaseNodeTypeDocument
from npc_engine.type_registry.contracts import RuntimeEdgeTypeDefinition, RuntimeFieldDefinition
from npc_engine.utils.errors import RegistryValidationError


YAML_GLOB = "*.yaml"

# node_type is the registry key: snake_case, and the form base_edges/*.yaml reference in
# src_type/dst_type. label is the Cypher label; it is backtick-escaped by cypher_identifier
# at every call site, and constrained here so a malformed value fails at load, not in a query.
NODE_TYPE_PATTERN = re.compile(r"[a-z][a-z0-9_]*")
NODE_LABEL_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _normalize_src_type(src_type: str | list[str]) -> str | tuple[str, ...]:
    """Normalize src_type to a single string or an ordered tuple of strings."""
    if isinstance(src_type, list):
        return tuple(t.strip().lower() for t in src_type)
    return src_type.strip().lower()


def load_base_node_types() -> MappingProxyType[str, MappingProxyType[str, RuntimeFieldDefinition]]:
    """Load package-shipped base node contract files into immutable runtime definitions."""

    directory = Path(__file__).resolve().parent / "base_nodes"
    loaded: dict[str, MappingProxyType[str, RuntimeFieldDefinition]] = {}
    for path in sorted(directory.glob(YAML_GLOB)):
        document = _load_node_document(path=path)
        node_key = document.node_type.strip().lower()
        if node_key in loaded:
            raise RegistryValidationError(source=str(path), detail=f"duplicate base node type: {node_key}")
        loaded[node_key] = _build_runtime_fields(document.fields)
    return MappingProxyType(loaded)


def load_base_node_labels() -> MappingProxyType[str, str]:
    """Load the declared Cypher label for every package-shipped base node kind.

    Additive companion to load_base_node_types (M1.2): the field maps are unchanged and
    their eight consumers are untouched. This reads the same files for the one piece of
    information the field maps discard — the label the generic write path must emit so it
    agrees with graph/'s hand-written Cypher.

    Returns:
        Immutable mapping of registry key (snake_case node_type) to Cypher label.

    Raises:
        RegistryValidationError: If a contract file is unreadable, fails schema validation,
            declares a non-identifier node_type or label, or duplicates a node type.
    """

    directory = Path(__file__).resolve().parent / "base_nodes"
    loaded: dict[str, str] = {}
    for path in sorted(directory.glob(YAML_GLOB)):
        document = _load_node_document(path=path)
        node_key = document.node_type.strip().lower()
        if node_key in loaded:
            raise RegistryValidationError(source=str(path), detail=f"duplicate base node type: {node_key}")
        loaded[node_key] = document.label
    return MappingProxyType(loaded)


def load_base_edge_types() -> MappingProxyType[str, RuntimeEdgeTypeDefinition]:
    """Load package-shipped base edge contract files into immutable runtime definitions."""

    directory = Path(__file__).resolve().parent / "base_edges"
    loaded: dict[str, RuntimeEdgeTypeDefinition] = {}
    for path in sorted(directory.glob(YAML_GLOB)):
        document = _load_edge_document(path=path)
        edge_key = document.edge_type.strip().upper()
        if edge_key in loaded:
            raise RegistryValidationError(source=str(path), detail=f"duplicate base edge type: {edge_key}")
        loaded[edge_key] = RuntimeEdgeTypeDefinition(
            src_type=_normalize_src_type(document.src_type),
            dst_type=document.dst_type.strip().lower(),
            directional=document.directional,
            cascade_on_delete=tuple(document.cascade_on_delete),
            fields=_build_runtime_fields(document.fields),
        )
    return MappingProxyType(loaded)


def _load_node_document(*, path: Path) -> BaseNodeTypeDocument:
    source = str(path)
    loaded = _load_yaml(path=path, source=source)
    try:
        document = BaseNodeTypeDocument.model_validate(loaded)
    except ValidationError as error:
        raise RegistryValidationError(source=source, detail=str(error)) from error
    _validate_node_identifiers(document=document, source=source)
    return document


def _validate_node_identifiers(*, document: BaseNodeTypeDocument, source: str) -> None:
    """Reject a base node contract whose key or label is not a strict identifier.

    ``label`` reaches Cypher through resolve_node_label, so a YAML file is the one place a
    file-supplied value could enter a query. cypher_identifier() backtick-escapes it
    downstream and remains the injection guard; this is the fail-fast boundary check that
    keeps a malformed label from ever getting that far.

    Args:
        document: Parsed base node contract.
        source: Path string used for error attribution.

    Raises:
        RegistryValidationError: If node_type is not snake_case or label is not a bare
            identifier.
    """

    if not NODE_TYPE_PATTERN.fullmatch(document.node_type):
        raise RegistryValidationError(
            source=source,
            detail=f"node_type must be snake_case matching {NODE_TYPE_PATTERN.pattern}: {document.node_type!r}",
        )
    if not NODE_LABEL_PATTERN.fullmatch(document.label):
        raise RegistryValidationError(
            source=source,
            detail=f"label must be a bare identifier matching {NODE_LABEL_PATTERN.pattern}: {document.label!r}",
        )


def _load_edge_document(*, path: Path) -> BaseEdgeTypeDocument:
    source = str(path)
    loaded = _load_yaml(path=path, source=source)
    try:
        return BaseEdgeTypeDocument.model_validate(loaded)
    except ValidationError as error:
        raise RegistryValidationError(source=source, detail=str(error)) from error


def _load_yaml(*, path: Path, source: str) -> dict[str, object]:
    try:
        return load_yaml_mapping(path=path, root_error_message="base registry contract root must be a YAML object")
    except (OSError, UnicodeError) as error:
        raise RegistryValidationError(source=source, detail=str(error)) from error
    except (ValueError, yaml.YAMLError) as error:
        raise RegistryValidationError(source=source, detail=str(error)) from error


def _build_runtime_fields(fields: dict[str, BaseFieldConfig]) -> MappingProxyType[str, RuntimeFieldDefinition]:
    runtime_fields = {
        field_name: RuntimeFieldDefinition(
            field_type=field_config.type,
            required=field_config.required,
            range_limits=_range_limits(field=field_config),
            default=field_config.default,
            description=field_config.description,
            semantics=tuple(),
            indexed=field_config.indexed,
            max_bytes=field_config.max_bytes,
            list_item_type=field_config.items_type,
            dict_value_type=field_config.values_type,
        )
        for field_name, field_config in fields.items()
    }
    return MappingProxyType(runtime_fields)


def _range_limits(*, field: BaseFieldConfig) -> tuple[int | float, int | float] | None:
    if field.range is None:
        return None
    return (field.range[0], field.range[1])
