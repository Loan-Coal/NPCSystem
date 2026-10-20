"""
test_faction_standings_route.py - Unit tests for GET /factions/{id}/standings.

Does NOT: use a real Neo4j connection or real FactionService.

Dependencies injected: FactionService stub via FastAPI dependency_overrides.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_faction_service
from npc_engine.api.routes.faction_politics import factions as route_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(standings: list[dict[str, Any]]) -> Any:
    """Return a minimal FactionService stub whose list_standings returns *standings*."""
    svc = AsyncMock()
    svc.list_standings = AsyncMock(return_value=standings)
    return svc


def _client(standings: list[dict[str, Any]]) -> TestClient:
    app = FastAPI()
    app.include_router(route_mod.router)
    svc = _make_service(standings)
    app.dependency_overrides[get_faction_service] = lambda: svc
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_standings_returns_200_with_target_string_and_target_name() -> None:
    """Route returns 200; each row carries target (str id) and target_name."""
    rows = [
        {"target": "fb", "target_name": "Faction Beta", "standing": 80},
        {"target": "fc", "target_name": "Faction Gamma", "standing": -30},
    ]
    resp = _client(rows).get("/factions/fa/standings")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    assert data[0]["target"] == "fb"
    assert data[0]["target_name"] == "Faction Beta"
    assert data[0]["standing"] == 80
    assert data[1]["target"] == "fc"
    assert data[1]["target_name"] == "Faction Gamma"


def test_standings_returns_empty_list_when_no_edges() -> None:
    """Route returns 200 with an empty data list when the faction has no standings."""
    resp = _client([]).get("/factions/isolated/standings")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_faction_standing_row_target_name_is_declared_field() -> None:
    """FactionStandingRow declares target_name as a named field, not stored as extra."""
    from npc_engine.api.routes.faction_politics.factions import FactionStandingRow

    assert "target_name" in FactionStandingRow.model_fields, (
        "target_name must be a declared field, not stored as model_extra"
    )
