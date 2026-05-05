"""
test_quest_routes_v14.py - Unit tests for P3 quest route wiring and provenance validation.

Does NOT: execute real graph writes.

Dependencies injected: FastAPI dependency overrides.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_db_session, get_quest_lifecycle_engine
from npc_engine.api.routes import quest
from npc_engine.config import Settings


class _FakeQuestEngine:
    async def offer_quest(self, **kwargs):
        return {"quest_id": kwargs["quest_id"], "player_id": kwargs["player_id"], "status": "offered"}

    async def accept_quest(self, **kwargs):
        return {"quest_id": kwargs["quest_id"], "player_id": kwargs["player_id"], "status": "accepted"}

    async def update_objective(self, **kwargs):
        return {"quest_id": kwargs["quest_id"], "player_id": kwargs["player_id"], "status": "in_progress"}

    async def evaluate_completion(self, **kwargs):
        return {"quest_id": kwargs["quest_id"], "player_id": kwargs["player_id"], "status": "completed"}

    async def apply_rewards(self, **kwargs):
        return {
            "quest_id": kwargs["quest_id"],
            "player_id": kwargs["player_id"],
            "status": "completed",
            "rewards_applied": True,
        }


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(quest.router, prefix="/v1")

    async def _db_session_stub() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_db_session] = _db_session_stub
    app.dependency_overrides[quest.get_settings] = lambda: Settings(API_KEY_SECRET="local_dev_secret_change_this_2026")
    app.dependency_overrides[get_quest_lifecycle_engine] = lambda: _FakeQuestEngine()
    return app


def _headers() -> dict[str, str]:
    return {
        "X-Request-ID": "req-quest-route-1",
        "X-Idempotency-Key": "idem-quest-route-1",
        "X-Idempotency-Request-Hash": "hash-quest-route-1",
    }


def test_quest_offer_route_dispatches_to_engine() -> None:
    client = TestClient(_build_app())
    response = client.post(
        "/v1/quest/offer",
        json={
            "quest_id": "quest-1",
            "player_id": "player-1",
            "title": "Find herbs",
            "objectives": [{"objective_id": "obj-1", "target_count": 1}],
            "item_rewards": [{"item_id": "item-1", "quantity": 1}],
            "currency_reward": {"amount": 10},
        },
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["quest_state"]["status"] == "offered"


def test_quest_route_rejects_missing_idempotency_request_hash() -> None:
    client = TestClient(_build_app())
    headers = _headers()
    headers.pop("X-Idempotency-Request-Hash")
    response = client.post(
        "/v1/quest/accept",
        json={"quest_id": "quest-1", "player_id": "player-1"},
        headers=headers,
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["success"] is False
    assert payload["detail"]["error"] == "QUEST_PROVENANCE_REQUIRED"
