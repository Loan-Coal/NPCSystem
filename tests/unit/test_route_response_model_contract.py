"""
Module: test_route_response_model_contract
Layer: test
Purpose: S20.6 exit contract — every HTTP route emits a typed OpenAPI body.
         Asserts (1) every in-schema APIRoute carries a response_model
         (excluding GET /health and the WebSocket route), and (2) the generated
         OpenAPI spec has a non-empty success-response schema for each operation
         (no route body serialises to an empty `{}`). Closes ISSUE-052.
Dependencies: unittest.mock, fastapi, npc_engine.main, npc_engine.config
Used by: pytest (unit suite)
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.routing import APIRoute

from npc_engine.config import Settings

_MINIMAL_SETTINGS = Settings(
    NEO4J_URI="bolt://localhost:7687",
    API_KEY_SECRET="test-contract-key-000",
)

# GET /health stays minimal by contract; WebSocket routes are not APIRoutes.
_EXEMPT_PATHS = frozenset({"/health"})
_SUCCESS_CODES = ("200", "201", "202")


def _build_app():
    """Build the app with minimal settings (no DB/LLM calls on construction)."""
    with patch("npc_engine.main.get_settings", return_value=_MINIMAL_SETTINGS):
        from npc_engine.main import create_app

        return create_app()


def _documented_api_routes(app) -> list[APIRoute]:
    """Return in-schema HTTP routes excluding the exempt paths."""
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.include_in_schema
        and route.path not in _EXEMPT_PATHS
    ]


def test_every_route_declares_a_response_model() -> None:
    """No documented HTTP route may be missing `response_model` (ISSUE-052)."""
    app = _build_app()
    missing = [
        f"{sorted(route.methods or [])} {route.path}"
        for route in _documented_api_routes(app)
        if route.response_model is None
    ]
    assert not missing, f"routes missing response_model: {missing}"


def test_openapi_success_responses_have_non_empty_schema() -> None:
    """Each documented operation's success body must carry a non-empty schema."""
    app = _build_app()
    spec = app.openapi()
    empty: list[str] = []
    for path, operations in spec["paths"].items():
        if path in _EXEMPT_PATHS:
            continue
        for method, operation in operations.items():
            responses = operation.get("responses", {})
            success = next((responses[c] for c in _SUCCESS_CODES if c in responses), None)
            if success is None:
                continue
            schema = success.get("content", {}).get("application/json", {}).get("schema")
            if not schema:
                empty.append(f"{method.upper()} {path}")
    assert not empty, f"operations with empty success-response schema: {empty}"


def test_openapi_components_include_ok_envelope() -> None:
    """The OkEnvelope generic must surface as a referenced component schema."""
    app = _build_app()
    spec = app.openapi()
    schema_names = spec.get("components", {}).get("schemas", {})
    assert any(name.startswith("OkEnvelope") for name in schema_names), (
        "expected at least one OkEnvelope_* component schema in the OpenAPI spec"
    )
