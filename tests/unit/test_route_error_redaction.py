"""
test_route_error_redaction.py - Regression tests for SEV-16 (no internal exception leak).

Does NOT: execute real graph writes or LLM calls.

Dependencies injected: FastAPI dependency overrides + monkeypatched service stubs.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.dependency_singletons import (
    get_quest_generation_engine,
    get_tick_scheduler,
)
from npc_engine.api.routes import clock, debts, groups, quest_generation
from npc_engine.config import Settings, get_settings

# Sentinels that must never appear in a client-facing response body.
_LEAK_HOST = "bolt://internal-neo4j:7687"
_LEAK_PATH = "/srv/npc_engine/prompts/quest_templates"
_LEAK_TOKENS = (_LEAK_HOST, _LEAK_PATH, "RuntimeError", "ValueError", "Neo.ClientError")


async def _db_session_stub() -> AsyncIterator[object]:
    yield object()


def _settings() -> Settings:
    return Settings(
        API_KEY_SECRET="local_dev_secret_change_this_2026",
        CLOCK_MODE="game_driven",
    )


def _assert_no_leak(body: str) -> None:
    for token in _LEAK_TOKENS:
        assert token not in body, f"response leaked internal token: {token!r}"


def test_clock_500_does_not_leak_exception_text() -> None:
    class _BoomScheduler:
        async def advance(self, **kwargs):
            raise RuntimeError(f"{_LEAK_HOST} refused (Neo.ClientError)")

    app = FastAPI()
    app.include_router(clock.router)
    app.dependency_overrides[get_db_session] = _db_session_stub
    app.dependency_overrides[get_tick_scheduler] = lambda: _BoomScheduler()
    app.dependency_overrides[get_settings] = _settings

    response = TestClient(app, raise_server_exceptions=False).post(
        "/clock/advance", json={"delta_ticks": 1, "game_time_seconds": 1}
    )

    assert response.status_code == 500
    _assert_no_leak(json.dumps(response.json()))


def test_debt_value_error_does_not_leak_exception_text(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom_create_debt(*args, **kwargs):
        raise ValueError(f"node lookup failed at {_LEAK_HOST}")

    monkeypatch.setattr(debts, "create_debt", _boom_create_debt)
    app = FastAPI()
    app.include_router(debts.router)
    app.dependency_overrides[get_db_session] = _db_session_stub

    response = TestClient(app).post(
        "/debts/debtor-1", json={"creditor_id": "c-1", "kind": "money", "magnitude": "10"}
    )

    assert response.status_code == 422
    _assert_no_leak(json.dumps(response.json()))


def test_group_exception_does_not_leak_exception_text(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom_add_member(*args, **kwargs):
        raise RuntimeError(f"{_LEAK_HOST} write timeout")

    monkeypatch.setattr(groups, "add_member", _boom_add_member)
    app = FastAPI()
    app.include_router(groups.router)
    app.dependency_overrides[get_db_session] = _db_session_stub

    response = TestClient(app).post(
        "/groups/group-1/members",
        json={"character_id": "char-1", "role": "member", "joined_at_tick": 0, "commitment": 10},
    )

    assert response.status_code == 422
    _assert_no_leak(json.dumps(response.json()))


def test_quest_generation_value_error_does_not_leak_path(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BoomEngine:
        async def generate(self, **kwargs):
            raise ValueError(f"no quest template YAML files found in {_LEAK_PATH}")

    app = FastAPI()
    app.include_router(quest_generation.router)
    app.dependency_overrides[get_db_session] = _db_session_stub
    app.dependency_overrides[get_quest_generation_engine] = lambda: _BoomEngine()

    response = TestClient(app).post("/quests/generate", json={"quest_giver_id": "npc-1"})

    assert response.status_code in (404, 422)
    _assert_no_leak(json.dumps(response.json()))
