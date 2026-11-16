"""
test_memory_consolidate_route.py - Unit tests for POST /memories/consolidate/{npc_id}.

RED anchors for T25.6:
  - route must pass body.turn_threshold to engine.consolidate();
  - LLM failure must produce a distinct payload status from threshold-not-met.

Does NOT: connect to Neo4j, call live LLM, or start the full application.
Dependencies injected: FastAPI dependency overrides.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependency_singletons import get_memory_consolidation_engine
from npc_engine.api.routes.knowledge.memories import router
from npc_engine.engines.memory_consolidation.memory_consolidation_engine import (
    ConsolidationResult,
)
from npc_engine.world.time_utils import TimePoint

# ---------------------------------------------------------------------------
# Engine spies / stubs
# ---------------------------------------------------------------------------


class _SpyEngine:
    """Records every consolidate() call; returns a successful result."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def consolidate(
        self,
        *,
        npc_id: str,
        game_time: TimePoint,
        turn_threshold: int | None = None,
    ) -> ConsolidationResult:
        """Record the kwargs and return a created result."""
        self.calls.append({"npc_id": npc_id, "turn_threshold": turn_threshold})
        return ConsolidationResult(memory_id="mem-t256", status="created")


class _LLMFailEngine:
    """Always returns an LLM-failure result regardless of turn count."""

    async def consolidate(
        self,
        *,
        npc_id: str,
        game_time: TimePoint,
        turn_threshold: int | None = None,
    ) -> ConsolidationResult:
        """Simulate an LLM error."""
        return ConsolidationResult(memory_id=None, status="llm_failed")


class _ThresholdNotMetEngine:
    """Always returns a threshold-not-met result."""

    async def consolidate(
        self,
        *,
        npc_id: str,
        game_time: TimePoint,
        turn_threshold: int | None = None,
    ) -> ConsolidationResult:
        """Simulate threshold not reached."""
        return ConsolidationResult(memory_id=None, status="threshold_not_met")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(engine: object) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    app.dependency_overrides[get_memory_consolidation_engine] = lambda: engine
    return TestClient(app)


# ---------------------------------------------------------------------------
# RED anchor 1 — route must forward body.turn_threshold to engine.consolidate()
# ---------------------------------------------------------------------------


def test_route_passes_turn_threshold_to_engine() -> None:
    """body.turn_threshold=3 must reach engine.consolidate(turn_threshold=3)."""
    spy = _SpyEngine()
    client = _build_app(spy)

    resp = client.post(
        "/v1/memories/consolidate/mira_innkeeper",
        json={"player_id": "player_demo", "turn_threshold": 3},
    )

    assert resp.status_code == 200
    assert spy.calls, "engine.consolidate() was never called"
    assert spy.calls[0]["turn_threshold"] == 3


def test_route_forwards_none_when_turn_threshold_omitted() -> None:
    """Omitting turn_threshold must forward None so the engine's configured value wins.

    A request-model default would silently override CONSOLIDATION_TURN_THRESHOLD
    (two sources of truth, rule 3).
    """
    spy = _SpyEngine()
    client = _build_app(spy)

    resp = client.post(
        "/v1/memories/consolidate/mira_innkeeper",
        json={"player_id": "player_demo"},
    )

    assert resp.status_code == 200
    assert spy.calls, "engine.consolidate() was never called"
    assert spy.calls[0]["turn_threshold"] is None


def test_route_rejects_non_positive_turn_threshold() -> None:
    """turn_threshold below 1 is invalid input and must be rejected at the boundary."""
    client = _build_app(_SpyEngine())

    resp = client.post(
        "/v1/memories/consolidate/mira_innkeeper",
        json={"player_id": "player_demo", "turn_threshold": 0},
    )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# RED anchor 2 — LLM failure must produce a distinct status from threshold-not-met
# ---------------------------------------------------------------------------


def test_llm_failure_returns_llm_failed_status() -> None:
    """When the engine returns status='llm_failed', the route payload must reflect it."""
    client = _build_app(_LLMFailEngine())

    resp = client.post(
        "/v1/memories/consolidate/mira_innkeeper",
        json={"player_id": "player_demo"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "llm_failed"
    assert data["memory_id"] is None


def test_threshold_not_met_returns_threshold_not_met_status() -> None:
    """When the engine returns status='threshold_not_met', payload must reflect it."""
    client = _build_app(_ThresholdNotMetEngine())

    resp = client.post(
        "/v1/memories/consolidate/mira_innkeeper",
        json={"player_id": "player_demo"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "threshold_not_met"
    assert data["memory_id"] is None


def test_llm_failure_and_threshold_not_met_statuses_differ() -> None:
    """LLM-failure and threshold-not-met must produce different status strings."""
    llm_client = _build_app(_LLMFailEngine())
    thr_client = _build_app(_ThresholdNotMetEngine())

    llm_resp = llm_client.post(
        "/v1/memories/consolidate/mira_innkeeper",
        json={"player_id": "player_demo"},
    )
    thr_resp = thr_client.post(
        "/v1/memories/consolidate/mira_innkeeper",
        json={"player_id": "player_demo"},
    )

    llm_status = llm_resp.json()["data"]["status"]
    thr_status = thr_resp.json()["data"]["status"]
    assert llm_status != thr_status
