"""
test_player_model_route.py - Unit tests for the player-model read route (F2.2).

Uses FastAPI dependency_overrides for the session and monkeypatches the graph reader
so no Neo4j is needed.

Dependencies injected: dummy session + monkeypatched get_player_model.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.routes.social import player_model as route_mod
from npc_engine.api.dependencies import get_db_session
from npc_engine.graph.character.player_model_writer import PlayerModelRecord


def _client(record: PlayerModelRecord | None, monkeypatch) -> TestClient:
    async def _fake_get(session, npc_id, player_id):
        return record

    monkeypatch.setattr(route_mod, "get_player_model", _fake_get)
    app = FastAPI()
    app.include_router(route_mod.router)
    app.dependency_overrides[get_db_session] = lambda: object()
    return TestClient(app)


def test_returns_perceived_trust_and_intent(monkeypatch) -> None:
    """The route surfaces the NPC's perceived_trust + perceived_intent for the player."""
    record = PlayerModelRecord(
        id="npc_a__player_1", npc_id="npc_a", player_id="player_1",
        perceived_trust=85, perceived_intent="friendly", last_updated_at="12",
    )
    data = _client(record, monkeypatch).get("/npc/npc_a/player-model/player_1").json()["data"]

    assert data["npc_id"] == "npc_a"
    assert data["player_id"] == "player_1"
    assert data["perceived_trust"] == 85
    assert data["perceived_intent"] == "friendly"


def test_missing_model_returns_404(monkeypatch) -> None:
    """When the NPC has no model of the player, the route returns 404."""
    response = _client(None, monkeypatch).get("/npc/npc_a/player-model/player_1")
    assert response.status_code == 404
