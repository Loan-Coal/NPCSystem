"""
test_system_registry_route.py - Unit tests for /v1/admin/schema/registry endpoint behavior.

Does NOT: start full application lifespan.

Dependencies injected: route dependency overrides.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

pytest.importorskip("neo4j")

from npc_engine.api.dependencies import get_type_registry
from npc_engine.api.routes.admin.system import admin_router
from npc_engine.type_registry.contracts import TypeRegistry


def _registry_stub() -> TypeRegistry:
    return TypeRegistry(schema_version="1.0")


def test_schema_registry_endpoint_returns_registry_snapshot() -> None:
    """Registry endpoint should return serialized registry snapshot envelope."""

    app = FastAPI()
    app.include_router(admin_router, prefix="/v1/admin")
    app.dependency_overrides[get_type_registry] = _registry_stub

    client = TestClient(app)
    response = client.get("/v1/admin/schema/registry")

    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["schema_version"] == "1.0"
    assert payload["data"]["node_types"] == []
    assert payload["data"]["edge_types"] == []
