"""
test_world_state_event_shock.py - Unit tests for world-state PATCH emotion shock.

When PATCH /v1/graph/nodes/world_state/<id> carries active_conditions whose IDs
(after stripping the _active suffix) match a severe Event node, NPCs at that
event's location must receive an emotion shock.  No Neo4j connection required.

Dependencies injected: FastAPI dependency overrides + monkeypatch.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable

from npc_engine.api.dependencies import get_db_session, get_generic_graph_service
from npc_engine.api.dependencies_stores import get_emotion_updater
from npc_engine.api.routes.admin import graph as route_mod
from npc_engine.config import get_settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_THRESHOLD = 50

_EVENT_SEVERE: dict = {
    "id": "market_fire",
    "severity": 60,
    "location_id": "loc_market_square",
    "event_type": "disaster",
    "tick_id": 1,
}

_EVENT_MILD: dict = {
    "id": "market_sale",
    "severity": 30,
    "location_id": "loc_market_square",
    "event_type": "commerce",
    "tick_id": 1,
}

# ---------------------------------------------------------------------------
# Stubs / spies
# ---------------------------------------------------------------------------


class _GraphServiceStub:
    """Stub holding one event node and a world-state node that PATCH updates."""

    def __init__(self, event: dict | None = None, previous_conditions: list[str] | None = None) -> None:
        self._event = event
        self._world: dict = {"id": "world", "tick_id": 5, "active_conditions": previous_conditions or []}

    async def patch_node(self, node_type: str, node_id: str, payload: dict) -> dict:
        """Merge the payload into the stored world-state node and return it."""
        self._world = {**self._world, **payload}
        return self._world

    async def get_node(self, node_type: str, node_id: str) -> dict | None:
        """Return the stored world-state node, or the seeded event when type and id match."""
        if node_type == "world_state":
            return self._world
        if (
            node_type == "event"
            and self._event is not None
            and self._event["id"] == node_id
        ):
            return self._event
        return None

    def missing_extension_warnings(self, node_type: str, node_payload: dict) -> list:
        """Return empty warnings."""
        return []


class _EmotionUpdaterSpy:
    """Records every apply_event_shock call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def apply_event_shock(self, npc_id: str, severity: int, tick: int) -> None:
        """Record the call."""
        self.calls.append({"npc_id": npc_id, "severity": severity, "tick": tick})


class _Settings:
    """Minimal settings stub."""

    RUMOR_EMOTION_SEVERITY_THRESHOLD: int = _THRESHOLD


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


class _FailingEmotionUpdater:
    """Raises the driver error a Neo4j outage produces during the write-through."""

    async def apply_event_shock(self, npc_id: str, severity: int, tick: int) -> None:
        """Simulate the emotion write failing after the world-state write succeeded."""
        raise ServiceUnavailable("neo4j down")


def _build_app(
    event: dict | None,
    npc_ids_at_location: list[str],
    emotion_spy: object,
    monkeypatch: pytest.MonkeyPatch,
    previous_conditions: list[str] | None = None,
) -> TestClient:
    async def _fake_chars_at_location(session, location_id: str) -> list[str]:
        return npc_ids_at_location

    monkeypatch.setattr(route_mod, "get_characters_at_location", _fake_chars_at_location)

    service = _GraphServiceStub(event, previous_conditions)
    app = FastAPI()
    app.include_router(route_mod.router, prefix="/v1")
    app.dependency_overrides[get_generic_graph_service] = lambda: service
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_emotion_updater] = lambda: emotion_spy
    app.dependency_overrides[get_settings] = lambda: _Settings()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_severe_event_shocks_npcs_at_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PATCH world_state with a severe condition must shock NPC at that event location."""
    spy = _EmotionUpdaterSpy()
    client = _build_app(_EVENT_SEVERE, ["aldric_merchant"], spy, monkeypatch)

    resp = client.patch(
        "/v1/graph/nodes/world_state/world",
        json={"properties": {
            "active_conditions": ["market_fire_active"],
            "epoch": "war",
            "last_updated_at": "t",
            "last_graph_updated_at": "t",
        }},
    )

    assert resp.status_code == 200
    assert len(spy.calls) == 1
    assert spy.calls[0]["npc_id"] == "aldric_merchant"
    assert spy.calls[0]["severity"] == 60


def test_mild_event_does_not_shock(monkeypatch: pytest.MonkeyPatch) -> None:
    """PATCH world_state with a mild event (below threshold) must NOT shock NPCs."""
    spy = _EmotionUpdaterSpy()
    client = _build_app(_EVENT_MILD, ["aldric_merchant"], spy, monkeypatch)

    resp = client.patch(
        "/v1/graph/nodes/world_state/world",
        json={"properties": {
            "active_conditions": ["market_sale_active"],
            "epoch": "war",
            "last_updated_at": "t",
            "last_graph_updated_at": "t",
        }},
    )

    assert resp.status_code == 200
    assert spy.calls == []


def test_no_matching_event_does_not_shock(monkeypatch: pytest.MonkeyPatch) -> None:
    """PATCH world_state with an unknown condition must not shock any NPC."""
    spy = _EmotionUpdaterSpy()
    client = _build_app(None, [], spy, monkeypatch)

    resp = client.patch(
        "/v1/graph/nodes/world_state/world",
        json={"properties": {
            "active_conditions": ["unknown_event_active"],
            "epoch": "war",
            "last_updated_at": "t",
            "last_graph_updated_at": "t",
        }},
    )

    assert resp.status_code == 200
    assert spy.calls == []


def _patch_conditions(client: TestClient, conditions: object):
    """PATCH the world-state node with *conditions* as active_conditions."""
    return client.patch(
        "/v1/graph/nodes/world_state/world",
        json={"properties": {
            "active_conditions": conditions,
            "epoch": "war",
            "last_updated_at": "t",
            "last_graph_updated_at": "t",
        }},
    )


def test_already_active_condition_does_not_shock_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """A condition active before the PATCH is not newly active: no second shock (T25.8)."""
    spy = _EmotionUpdaterSpy()
    client = _build_app(
        _EVENT_SEVERE, ["aldric_merchant"], spy, monkeypatch,
        previous_conditions=["market_fire_active"],
    )

    resp = _patch_conditions(client, ["market_fire_active"])

    assert resp.status_code == 200
    assert spy.calls == []


def test_repeated_patch_shocks_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """EventFire resends the full list each time; two identical PATCHes shock once."""
    spy = _EmotionUpdaterSpy()
    client = _build_app(_EVENT_SEVERE, ["aldric_merchant"], spy, monkeypatch)

    _patch_conditions(client, ["market_fire_active"])
    _patch_conditions(client, ["market_fire_active"])

    assert len(spy.calls) == 1


def test_shock_failure_after_write_returns_200_with_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """The world-state write already succeeded, so a shock failure must not become a 500.

    It is surfaced as a warning in meta, never swallowed.
    """
    client = _build_app(_EVENT_SEVERE, ["aldric_merchant"], _FailingEmotionUpdater(), monkeypatch)

    resp = _patch_conditions(client, ["market_fire_active"])

    assert resp.status_code == 200
    warnings = resp.json()["meta"]["warnings"]
    assert [w["warning_code"] for w in warnings] == ["EVENT_SHOCK_FAILED"]
    assert warnings[0]["npc_id"] == "aldric_merchant"


@pytest.mark.parametrize("bad", ["market_fire_active", [1, 2], {"a": 1}])
def test_malformed_active_conditions_is_rejected(monkeypatch: pytest.MonkeyPatch, bad: object) -> None:
    """active_conditions must be a list of strings; anything else is a 422, not a 500."""
    spy = _EmotionUpdaterSpy()
    client = _build_app(_EVENT_SEVERE, ["aldric_merchant"], spy, monkeypatch)

    resp = _patch_conditions(client, bad)

    assert resp.status_code == 422
    assert spy.calls == []


def test_witness_lookup_failure_after_write_returns_200_with_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neo4j error finding witnesses also lands after the write: a warning, not a 500 (T25.8 review)."""
    spy = _EmotionUpdaterSpy()
    client = _build_app(_EVENT_SEVERE, ["aldric_merchant"], spy, monkeypatch)

    async def _down(session, location_id: str) -> list[str]:
        raise ServiceUnavailable("neo4j down")

    monkeypatch.setattr(route_mod, "get_characters_at_location", _down)

    resp = _patch_conditions(client, ["market_fire_active"])

    assert resp.status_code == 200
    assert [w["warning_code"] for w in resp.json()["meta"]["warnings"]] == ["EVENT_SHOCK_FAILED"]
    assert spy.calls == []


def test_duplicate_conditions_shock_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same condition twice in one body is one event."""
    spy = _EmotionUpdaterSpy()
    client = _build_app(_EVENT_SEVERE, ["aldric_merchant"], spy, monkeypatch)

    _patch_conditions(client, ["market_fire_active", "market_fire_active"])

    assert len(spy.calls) == 1
