"""
test_relationship_route_phase.py - Unit tests for the relationship route returning
relationship_phase + phase_started_at_tick (F2.1).

Uses FastAPI dependency_overrides to inject a fake RelationReader so no Neo4j is needed.

Dependencies injected: fake RelationReader via dependency override.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.routes.relationship import router, _get_relation_reader
from npc_engine.graph.relation_phase_reader import RelationPhaseRow


class _FakeReader:
    def __init__(self, row: RelationPhaseRow | None) -> None:
        self._row = row

    async def get_relation_phase_row(self, *, src_id: str, dst_id: str) -> RelationPhaseRow | None:
        return self._row


def _client(row: RelationPhaseRow | None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_get_relation_reader] = lambda: _FakeReader(row)
    return TestClient(app)


def test_returns_phase_and_started_tick() -> None:
    """The endpoint surfaces standing plus the persisted phase and start tick."""
    row = RelationPhaseRow(
        trust=70, fear=5, affection=20, relationship_phase="FRIEND", phase_started_at_tick=12,
    )
    response = _client(row).get("/npc/npc_a/relationship/player_1")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["standing"] == "ALLIED"  # 70 + 20 - 5 = 85 -> ALLIED
    assert data["relationship_phase"] == "FRIEND"
    assert data["phase_started_at_tick"] == 12


def test_phase_null_when_never_transitioned() -> None:
    """relationship_phase + phase_started_at_tick are null when no transition is stored."""
    row = RelationPhaseRow(
        trust=0, fear=0, affection=0, relationship_phase=None, phase_started_at_tick=None,
    )
    data = _client(row).get("/npc/npc_a/relationship/player_1").json()["data"]

    assert data["relationship_phase"] is None
    assert data["phase_started_at_tick"] is None
    assert data["standing"] == "NEUTRAL"


def test_missing_edge_returns_404() -> None:
    """A missing RELATES_TO edge yields HTTP 404."""
    response = _client(None).get("/npc/npc_a/relationship/player_1")
    assert response.status_code == 404
