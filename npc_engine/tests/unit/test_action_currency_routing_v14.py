"""
test_action_currency_routing_v14.py - Unit tests for P2 buy/sell routing in action endpoint.

Does NOT: execute real graph writes.

Dependencies injected: dependency overrides and monkeypatch stubs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_db_session
from api.routes import action
from config import Settings


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(action.router, prefix="/v1")

    async def _db_session_stub() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_db_session] = _db_session_stub
    app.dependency_overrides[action.get_settings] = lambda: Settings(API_KEY_SECRET="local_dev_secret_change_this_2026")
    return app


def test_action_route_buy_item_uses_currency_coordinator(monkeypatch) -> None:
    called = {"value": False}

    async def fake_coordinator(**kwargs):
        called["value"] = True
        return {"request_id": "req-1", "amount": kwargs["amount"], "replayed": False}

    async def fake_relation_delta(**kwargs):
        raise AssertionError("relation delta path should not run for buy_item")

    monkeypatch.setattr("api.routes.action.apply_buy_sell_currency_transfer", fake_coordinator)
    monkeypatch.setattr("api.routes.action.apply_relation_delta", fake_relation_delta)

    client = TestClient(_build_app())
    response = client.post(
        "/v1/action",
        json={
            "player_id": "player",
            "npc_id": "npc",
            "action_type": "buy_item",
            "intensity": 20,
            "counterparty_id": "shop",
            "currency_amount": 25,
            "session_scope": "s1",
        },
        headers={"X-Idempotency-Key": "idem-1"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert called["value"] is True


def test_action_route_non_currency_path_still_uses_relation_delta(monkeypatch) -> None:
    called = {"relation": False}

    async def fake_coordinator(**kwargs):
        raise AssertionError("currency coordinator should not run for help")

    async def fake_relation_delta(**kwargs):
        called["relation"] = True

    monkeypatch.setattr("api.routes.action.apply_buy_sell_currency_transfer", fake_coordinator)
    monkeypatch.setattr("api.routes.action.apply_relation_delta", fake_relation_delta)

    client = TestClient(_build_app())
    response = client.post(
        "/v1/action",
        json={
            "player_id": "player",
            "npc_id": "npc",
            "action_type": "help",
            "intensity": 20,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert called["relation"] is True
