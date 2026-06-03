"""
Tests for SEV-13: canonical WorldState id must be "world" (not "world_demo").
Regression guard so the DEC-022 contract is never silently broken again.
"""
from __future__ import annotations

import unittest.mock as mock


def test_seed_world_state_id_is_world() -> None:
    """_WORLD_STATE_ID in seed.py must be 'world'."""
    from demo_game.seed import _WORLD_STATE_ID  # type: ignore[import]

    assert _WORLD_STATE_ID == "world", (
        f"Expected 'world' (DEC-022) but got {_WORLD_STATE_ID!r}. "
        "Changing this breaks epoch/active_conditions visibility to NPCs."
    )


def test_build_world_state_payload_uses_canonical_id() -> None:
    """build_world_state_payload must embed id='world'."""
    from demo_game.seed import build_world_state_payload  # type: ignore[import]

    payload = build_world_state_payload("peace", [])
    assert payload["id"] == "world", (
        f"payload['id']={payload['id']!r}; must be 'world' (DEC-022)."
    )


def test_put_world_state_request_body_id_is_world() -> None:
    """EngineClient.put_world_state must send id='world' and NOT clobber faction_standings."""
    from demo_game.client import EngineClient  # type: ignore[import]

    client = EngineClient.__new__(EngineClient)
    captured: list[dict] = []

    def fake_upsert(node_type: str, props: dict) -> dict:
        captured.append(props)
        return {}

    client.upsert_node = fake_upsert  # type: ignore[method-assign]
    client.put_world_state("war", ["northern_war_begins"])

    assert captured, "upsert_node was not called"
    body = captured[0]
    assert body["id"] == "world", (
        f"Request body id={body['id']!r}; must be 'world' (DEC-022)."
    )
    assert "faction_standings" not in body, (
        "put_world_state must NOT clobber faction_standings."
    )
    assert "time_of_day" not in body, (
        "put_world_state must NOT clobber time_of_day."
    )
    assert "weather" not in body, (
        "put_world_state must NOT clobber weather."
    )
