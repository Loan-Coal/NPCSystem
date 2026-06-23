"""
test_investigations_route.py - Unit tests for the investigations read route (H0.3).

Uses FastAPI dependency_overrides for the engine so no Neo4j is needed. The engine
holds its own graph port now (SEV-24), so the route no longer injects a session.

Dependencies injected: overridden InvestigationEngine singleton.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.routes.admin import investigations as route_mod
from npc_engine.api.dependencies_advanced import get_investigation_engine


class _FakeEngine:
    """Stub InvestigationEngine for testing — returns preset context dicts."""

    def __init__(self, context: dict | None = None) -> None:
        self._context = context or {}

    async def get_investigation_context(self, *, investigator_id, event_id):
        return self._context


def _client(context: dict | None, fake_engine: _FakeEngine | None = None) -> TestClient:
    if fake_engine is None:
        fake_engine = _FakeEngine(context)
    app = FastAPI()
    app.include_router(route_mod.router)
    app.dependency_overrides[get_investigation_engine] = lambda: fake_engine
    return TestClient(app)


_FULL_CONTEXT = {
    "evidence": [{"id": "ev1", "description": "bloody dagger"}],
    "witnesses": [{"subject": {"id": "npc_a"}, "witnessed_at_tick": 5}],
    "suspects": [{"suspect": {"id": "npc_b"}}],
    "deductions": [],
    "alibi_contradictions": [],
    "rumor_contradictions": [],
}


def test_returns_investigation_context() -> None:
    """On a found event, route returns all six context keys."""
    resp = _client(_FULL_CONTEXT).get("/investigations/detective_1/event_42")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "evidence" in data
    assert "witnesses" in data
    assert data["evidence"][0]["id"] == "ev1"


def test_returns_404_when_no_data() -> None:
    """When event has no evidence/witnesses/suspects, route returns 404."""
    empty = {
        "evidence": [],
        "witnesses": [],
        "suspects": [],
        "deductions": [],
        "alibi_contradictions": [],
        "rumor_contradictions": [],
    }
    resp = _client(empty).get("/investigations/detective_1/missing_event")
    assert resp.status_code == 404


def test_investigator_id_and_event_id_are_passed() -> None:
    """Route passes the correct investigator_id and event_id to the engine."""
    received: dict = {}

    class _CapturingEngine:
        async def get_investigation_context(self, *, investigator_id, event_id):
            received["investigator_id"] = investigator_id
            received["event_id"] = event_id
            return _FULL_CONTEXT

    tc = _client(None, fake_engine=_CapturingEngine())  # type: ignore[arg-type]
    tc.get("/investigations/sherlock/crime_001")
    assert received["investigator_id"] == "sherlock"
    assert received["event_id"] == "crime_001"
