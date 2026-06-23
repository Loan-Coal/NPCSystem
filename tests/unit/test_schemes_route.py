"""test_schemes_route.py - Unit tests for the NPC schemes read route (F2.3).

Uses FastAPI dependency_overrides for the session and monkeypatches the graph
reader so no Neo4j is needed.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.routes.faction_politics import schemes as route_mod
from npc_engine.api.dependencies import get_db_session
from npc_engine.graph.intrigue.scheme_reader import SchemeStepView, SchemeWithSteps


def _client(schemes: list[SchemeWithSteps], monkeypatch) -> TestClient:
    async def _fake_get(session, npc_id):
        return schemes

    monkeypatch.setattr(route_mod, "get_schemes_with_steps_for_npc", _fake_get)
    app = FastAPI()
    app.include_router(route_mod.router)
    app.dependency_overrides[get_db_session] = lambda: object()
    return TestClient(app)


def test_returns_schemes_with_steps_and_discovered_flag(monkeypatch) -> None:
    """The route surfaces each scheme's status, discovered flag, and ordered steps."""
    schemes = [
        SchemeWithSteps(
            scheme_id="lira__abc", goal="rob the vault", status="discovered",
            discovered=True,
            steps=[
                SchemeStepView(step_order=1, completed=True, summary="cased the vault"),
                SchemeStepView(step_order=2, completed=True, summary="bribed the guard"),
            ],
        ),
        SchemeWithSteps(
            scheme_id="vex__def", goal="spy on council", status="active",
            discovered=False, steps=[],
        ),
    ]
    data = _client(schemes, monkeypatch).get("/npc/lira/schemes").json()["data"]

    assert data["npc_id"] == "lira"
    assert len(data["schemes"]) == 2
    first = data["schemes"][0]
    assert first["discovered"] is True
    assert first["status"] == "discovered"
    assert [s["step_order"] for s in first["steps"]] == [1, 2]
    assert data["schemes"][1]["discovered"] is False
    assert data["schemes"][1]["steps"] == []


def test_npc_with_no_schemes_returns_empty_list(monkeypatch) -> None:
    """An NPC with no schemes yields an empty schemes list (not a 404)."""
    data = _client([], monkeypatch).get("/npc/quiet_npc/schemes").json()["data"]

    assert data["npc_id"] == "quiet_npc"
    assert data["schemes"] == []
