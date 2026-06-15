"""
Module: test_typed_payload_contract
Layer: test
Purpose: SEV-16 regression lock — every client/SDK-consumed route must expose a
         *named* payload schema for its envelope `data` field, not an opaque
         `dict[str, Any]`. Asserts the generated OpenAPI `data` property of each
         route in TARGETED_ROUTES references a component schema ($ref), directly
         or via array items. The sibling test_route_response_model_contract only
         checks the schema is non-empty, which `dict[str, Any]` already passes —
         this is the stronger gate that blocks regressions back to opaque dicts.
Dependencies: unittest.mock, fastapi, npc_engine.main, npc_engine.config
Used by: pytest (unit suite)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from npc_engine.config import Settings

_MINIMAL_SETTINGS = Settings(
    NEO4J_URI="bolt://localhost:7687",
    API_KEY_SECRET="test-contract-key-000",
)

_SUCCESS_CODES = ("200", "201", "202")

# (METHOD, PATH) of every route typed under SEV-16. Grown one tier per commit;
# every entry here must resolve its envelope `data` to a named component schema.
TARGETED_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        # Tier 1 — zero-risk rewires (typed model already existed in-file)
        ("get", "/v1/npc/{npc_id}/relationship/{other_id}"),
        ("get", "/v1/npc/{npc_id}/player-model/{player_id}"),
        # Tier 2 — fixed-shape single reads
        ("get", "/v1/chapters/current"),
        ("get", "/v1/investigations/{investigator_id}/{event_id}"),
        # Tier 3 — politics/social entity lists + reputation writes
        ("get", "/v1/admin/beliefs/{character_id}"),
        ("get", "/v1/admin/goals/{character_id}"),
        ("get", "/v1/admin/items/{character_id}"),
        ("get", "/v1/admin/memories/{character_id}"),
        ("post", "/v1/admin/memories/consolidate/{npc_id}"),
        ("get", "/v1/admin/pledges/characters/{character_id}"),
        ("get", "/v1/admin/treaties/factions/{faction_id}"),
        ("get", "/v1/admin/factions/"),
        ("get", "/v1/admin/factions/{faction_id}/standings"),
        ("get", "/v1/graph/characters/{character_id}/reputation"),
        ("put", "/v1/admin/characters/{character_id}/reputation/{faction_id}"),
        ("post", "/v1/admin/characters/{character_id}/reputation/{faction_id}/adjust"),
        # Tier 4 — gossip / economy / quest-generation
        ("post", "/v1/admin/gossip/spread"),
        ("get", "/v1/admin/gossip/trace/{event_id}"),
        ("post", "/v1/admin/gossip/correct"),
        ("get", "/v1/admin/economy/price"),
        ("post", "/v1/admin/economy/trade"),
        ("post", "/v1/admin/quests/generate"),
        ("get", "/v1/admin/quests/drafts"),
        ("post", "/v1/admin/quests/{quest_id}/offer"),
        ("get", "/v1/admin/quests/{quest_id}"),
        # Tier 5 — dashboard system lists
        ("get", "/v1/admin/system/engines"),
        ("get", "/v1/admin/system/events"),
    }
)


def _build_app():
    """Build the app with minimal settings (no DB/LLM calls on construction)."""
    with patch("npc_engine.main.get_settings", return_value=_MINIMAL_SETTINGS):
        from npc_engine.main import create_app

        return create_app()


def _resolve_ref(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Follow a single `$ref` into components/schemas; return schema unchanged otherwise."""
    ref = schema.get("$ref")
    if not ref:
        return schema
    name = ref.rsplit("/", 1)[-1]
    return spec.get("components", {}).get("schemas", {}).get(name, {})


def _data_schema_for(spec: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    """Return the resolved schema of the envelope `data` field for one operation."""
    operation = spec["paths"][path][method]
    responses = operation.get("responses", {})
    success = next((responses[c] for c in _SUCCESS_CODES if c in responses), None)
    assert success is not None, f"no success response for {method.upper()} {path}"
    envelope_ref = success["content"]["application/json"]["schema"]
    envelope = _resolve_ref(spec, envelope_ref)
    return envelope.get("properties", {}).get("data", {})


def _references_named_schema(data_schema: dict[str, Any]) -> bool:
    """True when `data` is a component $ref, or an array whose items are a $ref."""
    if "$ref" in data_schema:
        return True
    if data_schema.get("type") == "array":
        return "$ref" in data_schema.get("items", {})
    return False


def test_targeted_routes_expose_named_payload_schema() -> None:
    """Each SEV-16 route's envelope `data` must reference a named component schema."""
    spec = _build_app().openapi()
    opaque: list[str] = []
    for method, path in sorted(TARGETED_ROUTES):
        data_schema = _data_schema_for(spec, method, path)
        if not _references_named_schema(data_schema):
            opaque.append(f"{method.upper()} {path}: {data_schema}")
    assert not opaque, f"routes still expose an opaque dict payload: {opaque}"
