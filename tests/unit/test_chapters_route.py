"""
test_chapters_route.py - Unit tests for the chapters read route (H0.4).

Uses FastAPI dependency_overrides for the session and monkeypatches the graph
reader so no Neo4j is needed.

Dependencies injected: dummy session + monkeypatched get_current_chapter.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.routes import chapters as route_mod
from npc_engine.api.dependencies import get_db_session


_SAMPLE_CHAPTER = {
    "id": "chap_001",
    "name": "The Fall of Westmarch",
    "started_at_tick": 42,
    "theme": "conflict",
    "status": "open",
}


def _client(chapter: dict | None, monkeypatch) -> TestClient:
    async def _fake_get_current(session):
        return chapter

    monkeypatch.setattr(route_mod, "get_current_chapter", _fake_get_current)
    app = FastAPI()
    app.include_router(route_mod.router)
    app.dependency_overrides[get_db_session] = lambda: object()
    return TestClient(app)


def test_returns_current_chapter(monkeypatch) -> None:
    """Route returns the open chapter envelope with all fields."""
    resp = _client(_SAMPLE_CHAPTER, monkeypatch).get("/chapters/current")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "chap_001"
    assert data["name"] == "The Fall of Westmarch"
    assert data["started_at_tick"] == 42
    assert data["theme"] == "conflict"
    assert data["status"] == "open"


def test_returns_404_when_no_chapter(monkeypatch) -> None:
    """When no chapter node is open, route returns 404."""
    resp = _client(None, monkeypatch).get("/chapters/current")
    assert resp.status_code == 404
