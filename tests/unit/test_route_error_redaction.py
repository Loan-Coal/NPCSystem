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


def test_graph_error_to_http_redacts_node_identity() -> None:
    """L1-02: NodeNotFoundError must not leak node_type/node_id/class repr to the client."""
    from npc_engine.api.route_helpers import graph_error_to_http
    from npc_engine.utils.errors import NodeNotFoundError

    exc = graph_error_to_http(NodeNotFoundError(node_type="Character", node_id="secret_id_42"))
    assert exc.status_code == 404
    assert exc.detail == "Resource not found"
    for leaked in ("secret_id_42", "Character", "NodeNotFoundError"):
        assert leaked not in str(exc.detail), f"404 detail leaked {leaked!r}"


def test_graph_error_to_http_redacts_schema_path_but_keeps_validation_feedback() -> None:
    """L1-02: 422s expose caller-relevant feedback but never the internal schema path or class repr."""
    from npc_engine.api.route_helpers import graph_error_to_http
    from npc_engine.utils.errors import RegistryPayloadValidationError, SchemaValidationError

    reg = graph_error_to_http(
        RegistryPayloadValidationError(code="REQUIRED_FIELD_MISSING", detail="missing: epoch")
    )
    assert reg.status_code == 422
    assert "REQUIRED_FIELD_MISSING" in str(reg.detail) and "missing: epoch" in str(reg.detail)
    assert "RegistryPayloadValidationError" not in str(reg.detail)

    sch = graph_error_to_http(
        SchemaValidationError(schema_path="/srv/npc_engine/internal_schema.yaml", detail="bad enum value")
    )
    assert sch.status_code == 422
    assert str(sch.detail) == "bad enum value"
    assert "/srv/npc_engine" not in str(sch.detail)


def test_require_node_does_not_echo_node_type() -> None:
    """L1-08: require_node 404 must not echo the (URL-controlled) node_type label."""
    from fastapi import HTTPException

    from npc_engine.api.route_helpers import require_node

    with pytest.raises(HTTPException) as exc_info:
        require_node(None, node_type="SecretTypeLabel")

    assert exc_info.value.status_code == 404
    assert "SecretTypeLabel" not in str(exc_info.value.detail)


def test_locations_self_loop_does_not_leak_child_id() -> None:
    """L8-02: locations part_of self-loop 400 must not echo str(exc) (the child_id)."""
    from npc_engine.api.routes import locations

    app = FastAPI()
    app.include_router(locations.admin_router)
    app.dependency_overrides[get_db_session] = _db_session_stub

    response = TestClient(app).post(
        "/locations/leak_loc_77/part_of",
        json={"parent_id": "leak_loc_77", "hierarchy_level": 2},
    )

    assert response.status_code == 400
    assert "leak_loc_77" not in json.dumps(response.json())


def test_economy_trade_not_found_does_not_leak_node_id() -> None:
    """L8-02: economy trade NodeNotFoundError 422 must not echo exc.node_id."""
    from npc_engine.api.dependency_singletons import get_trade_engine
    from npc_engine.api.routes import economy
    from npc_engine.utils.errors import NodeNotFoundError

    class _BoomTrade:
        async def evaluate_offer(self, **kwargs):
            raise NodeNotFoundError(node_type="Character", node_id="secret_char_99")

    app = FastAPI()
    app.include_router(economy.router)
    app.dependency_overrides[get_db_session] = _db_session_stub
    app.dependency_overrides[get_trade_engine] = lambda: _BoomTrade()

    response = TestClient(app).post(
        "/economy/trade",
        json={
            "buyer_id": "b1", "seller_id": "s1", "item_id": "i1",
            "item_type": "sword", "offered_price": 10, "current_tick": 0,
        },
    )

    assert response.status_code == 422
    assert "secret_char_99" not in json.dumps(response.json())


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
