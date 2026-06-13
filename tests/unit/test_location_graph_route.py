"""
test_location_graph_route.py — Unit tests for api/routes/location_graph.py.

Tests the route layer only: 422 guards (invalid kind, self-loop), happy-path 201,
list and path endpoints. All Neo4j I/O is replaced by patching the graph query
functions imported by the route module.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.routes import location_graph


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------


def _build_app() -> FastAPI:
    """Build a minimal FastAPI app with only the location_graph router."""
    app = FastAPI()
    app.include_router(location_graph.router)

    async def _db_stub() -> AsyncIterator[object]:
        yield AsyncMock()

    app.dependency_overrides[get_db_session] = _db_stub
    return app


# ---------------------------------------------------------------------------
# POST /{from_id}/connects/{to_id} — happy path
# ---------------------------------------------------------------------------


def test_connect_locations_happy_path_returns_201() -> None:
    with patch(
        "npc_engine.api.routes.location_graph.create_connection",
        new=AsyncMock(return_value=None),
    ):
        client = TestClient(_build_app())
        response = client.post(
            "/locations/loc-a/connects/loc-b",
            json={"kind": "road", "travel_cost": 3, "is_open": True},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["from_id"] == "loc-a"
    assert data["to_id"] == "loc-b"
    assert data["kind"] == "road"
    assert data["travel_cost"] == 3
    assert data["is_open"] is True


def test_connect_locations_all_valid_kinds_accepted() -> None:
    for kind in ("road", "river", "sea", "secret"):
        with patch(
            "npc_engine.api.routes.location_graph.create_connection",
            new=AsyncMock(return_value=None),
        ):
            client = TestClient(_build_app())
            response = client.post(
                "/locations/loc-a/connects/loc-b",
                json={"kind": kind, "travel_cost": 1},
            )
        assert response.status_code == 201, f"kind={kind!r} should be accepted"


# ---------------------------------------------------------------------------
# POST /{from_id}/connects/{to_id} — invalid kind → 422
# ---------------------------------------------------------------------------


def test_connect_locations_invalid_kind_returns_422() -> None:
    client = TestClient(_build_app())
    response = client.post(
        "/locations/loc-a/connects/loc-b",
        json={"kind": "tunnel", "travel_cost": 2},
    )

    assert response.status_code == 422
    # FastAPI wraps HTTPException detail inside the response
    detail = response.json().get("detail", "")
    assert "kind" in str(detail).lower() or "tunnel" not in str(detail)


def test_connect_locations_empty_kind_returns_422() -> None:
    client = TestClient(_build_app())
    response = client.post(
        "/locations/loc-a/connects/loc-b",
        json={"kind": "", "travel_cost": 2},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /{from_id}/connects/{to_id} — self-loop → 422
# ---------------------------------------------------------------------------


def test_connect_locations_self_loop_returns_422() -> None:
    client = TestClient(_build_app())
    response = client.post(
        "/locations/loc-a/connects/loc-a",
        json={"kind": "road", "travel_cost": 1},
    )

    assert response.status_code == 422
    detail = response.json().get("detail", "")
    assert "itself" in str(detail).lower()


# ---------------------------------------------------------------------------
# POST /{from_id}/connects/{to_id} — travel_cost validation (Pydantic ge=1)
# ---------------------------------------------------------------------------


def test_connect_locations_zero_travel_cost_returns_422() -> None:
    client = TestClient(_build_app())
    response = client.post(
        "/locations/loc-a/connects/loc-b",
        json={"kind": "road", "travel_cost": 0},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /{location_id}/connections — happy path
# ---------------------------------------------------------------------------


def test_list_connections_returns_200_with_envelope() -> None:
    fake_connections = [
        {"destination_id": "loc-b", "destination_name": "Village", "kind": "road", "travel_cost": 2, "is_open": True}
    ]
    with patch(
        "npc_engine.api.routes.location_graph.get_connections_for_location",
        new=AsyncMock(return_value=fake_connections),
    ):
        client = TestClient(_build_app())
        response = client.get("/locations/loc-a/connections")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["connections"] == fake_connections


def test_list_connections_returns_empty_list_when_none() -> None:
    with patch(
        "npc_engine.api.routes.location_graph.get_connections_for_location",
        new=AsyncMock(return_value=[]),
    ):
        client = TestClient(_build_app())
        response = client.get("/locations/loc-isolated/connections")

    assert response.status_code == 200
    assert response.json()["data"]["connections"] == []


# ---------------------------------------------------------------------------
# GET /{from_id}/path/{to_id} — happy path
# ---------------------------------------------------------------------------


def test_shortest_path_returns_200_when_path_found() -> None:
    fake_path = {
        "node_ids": ["loc-a", "loc-b"],
        "hops": [{"kind": "road", "travel_cost": 3}],
        "total_cost": 3,
    }
    with patch(
        "npc_engine.api.routes.location_graph.get_shortest_path",
        new=AsyncMock(return_value=fake_path),
    ):
        client = TestClient(_build_app())
        response = client.get("/locations/loc-a/path/loc-b")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["node_ids"] == ["loc-a", "loc-b"]
    assert payload["data"]["total_cost"] == 3


def test_shortest_path_returns_404_when_no_path() -> None:
    with patch(
        "npc_engine.api.routes.location_graph.get_shortest_path",
        new=AsyncMock(return_value=None),
    ):
        client = TestClient(_build_app())
        response = client.get("/locations/loc-a/path/loc-z")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /{from_id}/connects/{to_id} — happy path
# ---------------------------------------------------------------------------


def test_remove_connection_returns_200() -> None:
    with patch(
        "npc_engine.api.routes.location_graph.delete_connection",
        new=AsyncMock(return_value=None),
    ):
        client = TestClient(_build_app())
        response = client.delete("/locations/loc-a/connects/loc-b")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["deleted"] is True
    assert payload["data"]["from_id"] == "loc-a"
    assert payload["data"]["to_id"] == "loc-b"
