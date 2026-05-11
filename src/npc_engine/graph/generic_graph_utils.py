"""
generic_graph_utils.py - Shared helpers for generic graph service encoding and Cypher safety.

Does NOT: execute graph queries.

Dependencies injected: None.
"""

import json
from datetime import datetime
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
        New dict with all Neo4j driver types converted to plain Python values and
        JSON-string dict fields parsed back into Python dicts.
    """

    decoded = {k: to_native(v) for k, v in data.items()}
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


def to_native(value: Any) -> Any:
    """Recursively convert Neo4j driver values to plain Python containers and scalars.

    Handles Neo4j DateTime objects (converted to ISO-8601 strings), dicts, lists,
    and any driver type that exposes a ``to_native()`` method.

    Args:
        value: A value returned by the Neo4j driver (may be a primitive, dict, list,
               datetime, or driver-specific type).

    Returns:
        Plain Python equivalent suitable for JSON serialisation.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_native(item) for item in value]
    _convert = getattr(value, "to_native", None)
    if callable(_convert):
        try:
            return to_native(_convert())
        except Exception:  # noqa: BLE001
            return value
    return value


def cypher_identifier(name: str) -> str:
    """Safely backtick-quote dynamic Cypher identifier names.

    Args:
        name: Raw identifier string that may contain special characters.

    Returns:
        Backtick-quoted Cypher identifier with any embedded backticks escaped.
    """

    return f"`{name.replace('`', '``')}`"
