"""
Tests for SEV-13: canonical WorldState id must be "world" (not "world_demo").
Regression guard so the DEC-022 contract is never silently broken again.
"""
from __future__ import annotations

import unittest.mock as mock


def test_build_world_state_payload_uses_canonical_id() -> None:
    """build_world_state_payload must embed id='world'."""
    from demo_game.seeds.seed import build_world_state_payload  # type: ignore[import]

    payload = build_world_state_payload("peace", [])
    assert payload.id == "world", (
        f"payload.id={payload.id!r}; must be 'world' (DEC-022)."
    )


def test_put_world_state_patches_canonical_world_node() -> None:
    """EngineClient.put_world_state must PATCH the canonical 'world' node and NOT clobber.

    Regression for L9-02: put_world_state previously called upsert_node (CREATE
    validation), which 422s on an existing world_state node because the generic
    create path requires faction_standings/time_of_day/weather. A partial PATCH
    preserves the SEV-13 no-clobber contract.
    """
    import json

    import httpx

    from demo_game.client import EngineClient

    captured: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method != "PATCH":
            raise AssertionError(f"put_world_state must PATCH, not {request.method} (L9-02)")
        captured.append(request)
        return httpx.Response(200, json={"data": {"epoch": "war"}})

    transport = httpx.MockTransport(_handler)
    http = httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer test"},
        transport=transport,
    )
    client = EngineClient(base_url="http://localhost:8000", api_key="test", _http_client=http)
    client.put_world_state("war", ["northern_war_begins"])

    assert captured, "PATCH was not called"
    req = captured[0]
    assert req.url.path == "/v1/graph/nodes/world_state/world", (
        f"path={req.url.path!r}; must target 'world_state/world' (DEC-022)."
    )
    props = json.loads(req.content).get("properties", {})
    assert "faction_standings" not in props, (
        "put_world_state must NOT clobber faction_standings."
    )
    assert "time_of_day" not in props, (
        "put_world_state must NOT clobber time_of_day."
    )
    assert "weather" not in props, (
        "put_world_state must NOT clobber weather."
    )
    assert props.get("epoch") == "war", "epoch must be included in the patch payload."
