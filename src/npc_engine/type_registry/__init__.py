"""
type_registry - Immutable graph type registry contracts, loaders, and payload validators.
Layer: config
Purpose: Immutable graph type registry contracts, loaders, and payload validators.
Public surface: (list re-exports here)

Does NOT: perform graph writes or execute request-time business logic.

Dependencies injected: None (package init re-exports public API).
"""

from __future__ import annotations

from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.type_registry.registry import build_type_registry
from npc_engine.type_registry.validation import (
    RegistryOperation,
    validate_edge_endpoint_types,
    validate_edge_payload,
    validate_node_payload,
)

__all__ = [
    "TypeRegistry",
    "build_type_registry",
    "RegistryOperation",
    "validate_edge_endpoint_types",
    "validate_edge_payload",
    "validate_node_payload",
]
