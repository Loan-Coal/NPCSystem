"""
node_validator.py - Validates and normalises node property dicts against TypeRegistry models.
Layer: config
Purpose: (auto-detected — review)

Does NOT: write to the graph or enforce business rules.

Dependencies injected: TypeRegistry.
"""

from __future__ import annotations

from npc_engine.type_registry.contracts import TypeRegistry


def validate_node_write(registry: TypeRegistry, node_type: str, props: dict) -> dict:
    """Validate and normalise a raw props dict against the registry model for node_type.

    If the node_type has no registered model (e.g. it is an unregistered ad-hoc type),
    the dict is returned as-is so callers are not broken by missing registrations.

    Args:
        registry: Immutable type registry holding dynamic node models.
        node_type: Registry key for the node type (case-sensitive, matches registry keys).
        props: Raw property dict to validate.

    Returns:
        Validated, None-stripped dict suitable for graph node writes.

    Raises:
        pydantic.ValidationError: If props fail validation against the registered model.
    """
    model_cls = registry.node_models.get(node_type)
    if model_cls is None:
        return props
    return model_cls.model_validate(props).model_dump(exclude_none=True)
