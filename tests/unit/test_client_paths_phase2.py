"""
test_client_paths_phase2.py - Unit tests for Phase 2 client path fixes.

Verifies that EngineClient sends requests to the correct URLs for economy
and quest endpoints. Uses httpx.MockTransport to intercept calls without
hitting a real server.

Does NOT: test business logic, response parsing beyond path correctness.
Dependencies injected: httpx.MockTransport (no real network).
"""

from __future__ import annotations

import httpx
import pytest

from demo_game.client import EngineClient, EngineClientError


def _make_client(recorded: list[httpx.Request]) -> EngineClient:
    """Build an EngineClient backed by a mock transport that records requests."""

    def _handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(200, json={"data": {"price": 100}, "accepted": True})

    transport = httpx.MockTransport(_handler)
    http = httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer test"},
        transport=transport,
    )
    return EngineClient(
        base_url="http://localhost:8000",
        api_key="test",
        _http_client=http,
    )


# ---------------------------------------------------------------------------
# Economy paths
# ---------------------------------------------------------------------------

def test_get_item_price_uses_admin_path() -> None:
    recorded: list[httpx.Request] = []
    client = _make_client(recorded)
    client.get_item_price("spice", "aldric_merchant")
    assert len(recorded) == 1
    assert recorded[0].url.path == "/v1/admin/economy/price"


def test_post_trade_uses_admin_path() -> None:
    recorded: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(200, json={"data": {"accepted": True}})

    transport = httpx.MockTransport(_handler)
    http = httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer test"},
        transport=transport,
    )
    client = EngineClient(base_url="http://localhost:8000", api_key="test", _http_client=http)
    client.post_trade(
        buyer_id="player",
        seller_id="aldric_merchant",
        item_id="northern_spice_bundle",
        item_type="spice",
        offered_price=80,
        tick=0,
    )
    assert len(recorded) == 1
    assert recorded[0].url.path == "/v1/admin/economy/trade"


# ---------------------------------------------------------------------------
# Quest generation / fetch paths (admin)
# ---------------------------------------------------------------------------

def test_post_quest_generate_uses_admin_path() -> None:
    recorded: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(200, json={"data": {"quest_id": "q_123"}})

    transport = httpx.MockTransport(_handler)
    http = httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer test"},
        transport=transport,
    )
    client = EngineClient(base_url="http://localhost:8000", api_key="test", _http_client=http)
    client.post_quest_generate("aldric_merchant")
    assert len(recorded) == 1
    assert recorded[0].url.path == "/v1/admin/quests/generate"


def test_get_quest_uses_admin_path() -> None:
    recorded: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(200, json={"data": {"quest_id": "q_123", "status": "offered"}})

    transport = httpx.MockTransport(_handler)
    http = httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer test"},
        transport=transport,
    )
    client = EngineClient(base_url="http://localhost:8000", api_key="test", _http_client=http)
    client.get_quest("q_123")
    assert len(recorded) == 1
    assert recorded[0].url.path == "/v1/admin/quests/q_123"


def test_get_quest_returns_none_on_404() -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(_handler)
    http = httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer test"},
        transport=transport,
    )
    client = EngineClient(base_url="http://localhost:8000", api_key="test", _http_client=http)
    result = client.get_quest("missing_quest")
    assert result is None


# ---------------------------------------------------------------------------
# Quest accept path (singular /v1/quest/)
# ---------------------------------------------------------------------------

def test_post_quest_accept_uses_singular_quest_path() -> None:
    recorded: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(200, json={"data": {"status": "accepted"}})

    transport = httpx.MockTransport(_handler)
    http = httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer test"},
        transport=transport,
    )
    client = EngineClient(base_url="http://localhost:8000", api_key="test", _http_client=http)
    client.post_quest_accept("q_123", "player")
    assert len(recorded) == 1
    assert recorded[0].url.path == "/v1/quest/accept"


# ---------------------------------------------------------------------------
# post_quest_offer is a seed-helper on EngineClient (added back in Phase 4)
# ---------------------------------------------------------------------------

def test_post_quest_offer_is_seed_helper() -> None:
    # Phase 4: post_quest_offer re-added as a seeder convenience for
    # deterministic quest creation in seed.py. It posts to /v1/quest/offer
    # with required idempotency headers.
    client = EngineClient(base_url="http://localhost:8000", api_key="test")
    assert hasattr(client, "post_quest_offer"), (
        "post_quest_offer must exist — it is used by seed.py for deterministic quest seeding"
    )
