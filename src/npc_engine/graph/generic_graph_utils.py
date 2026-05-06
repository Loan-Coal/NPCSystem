"""
generic_graph_utils.py - Shared helpers for generic graph service encoding and Cypher safety.

Does NOT: execute graph queries.

Dependencies injected: None.
"""

import json
from typing import Any, Mapping

from npc_engine.type_registry.contracts import RuntimeFieldDefinition
from npc_engine.utils.errors import RegistryPayloadValidationError


BASE_NODE_LABELS = {
    "character": "Character",
    "event": "Event",
    "location": "Location",
    "world_state": "WorldState",
}


def required_node_id(payload: dict[str, Any]) -> str:
    """Return non-empty node id from payload or raise typed validation error.

    Args:
        payload: Node property dict expected to contain an "id" key.

    Returns:
        Non-empty string node id.

    Raises:
        RegistryPayloadValidationError: If "id" is missing, not a string, or blank.
    """

    node_id = payload.get("id")
    if isinstance(node_id, str) and node_id.strip():
        return node_id
    raise RegistryPayloadValidationError(code="NODE_ID_REQUIRED", detail="node payload requires non-empty id")


def encode_properties(data: Mapping[str, Any], fields: Mapping[str, RuntimeFieldDefinition]) -> dict[str, Any]:
    """Encode runtime values for database persistence using field contracts.

    Args:
        data: Raw property dict to encode.
        fields: Field definitions from the type registry keyed by field name.

    Returns:
        New dict with dict-typed fields serialized as JSON strings; unknown fields excluded.
    """

    encoded: dict[str, Any] = {}
    for key, value in data.items():
        definition = fields.get(key)
        if definition is None:
            continue
        if definition.field_type == "dict" and value is not None:
            encoded[key] = json.dumps(value, sort_keys=True)
            continue
        encoded[key] = value
    return encoded


def decode_properties(data: Mapping[str, Any], fields: Mapping[str, RuntimeFieldDefinition]) -> dict[str, Any]:
    """Decode stored values into API-friendly representations using field contracts.

    Args:
        data: Raw property dict as read from the graph (dict-typed fields may be JSON strings).
        fields: Field definitions from the type registry keyed by field name.

    Returns:
        New dict with JSON-string dict fields parsed back into Python dicts.
    """

    decoded = dict(data)
    for key, definition in fields.items():
        if definition.field_type != "dict":
            continue
        raw_value = decoded.get(key)
        if not isinstance(raw_value, str):
            continue
        try:
            decoded[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            continue
    return decoded


def resolve_node_label(node_type: str) -> str:
    """Resolve graph label for base and custom node types.

    Args:
        node_type: Node type key (e.g. "character") or custom type name.

    Returns:
        Cypher node label string (e.g. "Character"); falls back to node_type if not in base map.
    """

    node_key = node_type.strip().lower()
    return BASE_NODE_LABELS.get(node_key, node_type)


def cypher_identifier(name: str) -> str:
    """Safely backtick-quote dynamic Cypher identifier names.

    Args:
        name: Raw identifier string that may contain special characters.

    Returns:
        Backtick-quoted Cypher identifier with any embedded backticks escaped.
    """

    return f"`{name.replace('`', '``')}`"
