"""
test_graph_warning_pipeline.py - Unit tests for graph warning metadata and observability.

Does NOT: execute graph queries.

Dependencies injected: FastAPI dependency overrides.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

pytest.importorskip("neo4j")

from npc_engine.api.dependencies import get_generic_graph_service
from npc_engine.api.routes.graph import router as graph_router
from npc_engine.utils.errors import RegistryPayloadValidationError
from npc_engine.utils.metrics import get_counter_value, reset_metrics_registry


class _ServiceStub:
    async def get_node(self, node_type: str, node_id: str):
        return {"id": node_id}

    async def list_nodes(self, node_type: str, limit: int, offset: int):
        return [{"id": "c1"}]

    async def upsert_node(self, node_type: str, payload: dict):
        return {"id": payload.get("id", "c1")}

    async def patch_node(self, node_type: str, node_id: str, payload: dict):
        return {"id": node_id}

    async def get_edge(self, edge_type: str, src_id: str, dst_id: str):
        return {"src_id": src_id, "dst_id": dst_id}

    async def list_edges(self, edge_type: str, limit: int, offset: int, src_id=None, dst_id=None):
        return []

    async def upsert_edge(self, edge_type: str, src_id: str, dst_id: str, payload: dict):
        return {"src_id": src_id, "dst_id": dst_id}

    async def delete_edge(self, edge_type: str, src_id: str, dst_id: str):
        return True

    def missing_extension_warnings(self, node_type: str, node_payload: dict):
        return [
            {
                "warning_code": "MISSING_EXTENSION_VALUE",
                "type": "extension_missing_value",
                "message": "missing extension value for character.reputation",
                "node_type": "character",
                "field_name": "reputation",
            }
        ]


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(graph_router, prefix="/v1")
    app.dependency_overrides[get_generic_graph_service] = lambda: _ServiceStub()
    return app


def setup_function() -> None:
    reset_metrics_registry()


def test_node_upsert_emits_warning_meta_and_metrics() -> None:
    """Node upsert response should include warning metadata and increment warning counters."""

    client = TestClient(_build_app())

    response = client.post("/v1/graph/nodes/character", json={"properties": {"id": "c1", "name": "Aria"}})

    payload = response.json()
    warnings = payload["meta"]["warnings"]
    warning_count = get_counter_value(
        "graph_warnings_total",
        labels={"warning_code": "missing_extension_value", "route": "graph"},
    )

    assert response.status_code == 200
    assert len(warnings) == 1
    assert warnings[0]["warning_code"] == "MISSING_EXTENSION_VALUE"
    assert warning_count == 1.0


class _ErrorServiceStub:
    """Service stub that raises RegistryPayloadValidationError for unknown types."""

    async def list_nodes(self, node_type: str, limit: int, offset: int):
        raise RegistryPayloadValidationError(code="NODE_TYPE_UNKNOWN", detail=f"unknown node type: {node_type}")

    async def list_edges(self, edge_type: str, limit: int, offset: int, src_id=None, dst_id=None):
        raise RegistryPayloadValidationError(code="EDGE_TYPE_UNKNOWN", detail=f"unknown edge type: {edge_type}")

    def missing_extension_warnings(self, node_type: str, node_payload: dict):
        return []


def _build_error_app() -> FastAPI:
    app = FastAPI()
    app.include_router(graph_router, prefix="/v1")
    app.dependency_overrides[get_generic_graph_service] = lambda: _ErrorServiceStub()
    return app


def test_list_nodes_unknown_type_returns_422() -> None:
    """GET /nodes/<unknown> must return 422, not 500 (regression: ISSUE-017)."""
    client = TestClient(_build_error_app())
    response = client.get("/v1/graph/nodes/WorldEvent")
    assert response.status_code == 422


def test_list_edges_unknown_type_returns_422() -> None:
    """GET /edges/<unknown> must return 422, not 500 (regression: ISSUE-017)."""
    client = TestClient(_build_error_app())
    response = client.get("/v1/graph/edges/FEARS")
    assert response.status_code == 422
