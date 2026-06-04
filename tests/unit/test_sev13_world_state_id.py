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


def test_put_world_state_patches_canonical_world_node() -> None:
    """EngineClient.put_world_state must PATCH the canonical 'world' node and NOT clobber.

    Regression for L9-02: put_world_state previously called upsert_node (CREATE
    validation), which 422s on an existing world_state node because the generic
    create path requires faction_standings/time_of_day/weather. A partial update
    must go through patch_node (PATCH validation), which only validates supplied
    fields against the existing node — preserving the SEV-13 no-clobber contract.
    """
    from demo_game.client import EngineClient  # type: ignore[import]

    client = EngineClient.__new__(EngineClient)
    captured: list[tuple[str, str, dict]] = []

    def fake_patch(node_type: str, node_id: str, props: dict) -> dict:
        captured.append((node_type, node_id, props))
        return {}

    def fail_upsert(node_type: str, props: dict) -> dict:  # pragma: no cover - guard
        raise AssertionError("put_world_state must PATCH, not upsert (L9-02)")

    client.patch_node = fake_patch  # type: ignore[method-assign]
    client.upsert_node = fail_upsert  # type: ignore[method-assign]
    client.put_world_state("war", ["northern_war_begins"])

    assert captured, "patch_node was not called"
    node_type, node_id, body = captured[0]
    assert node_type == "world_state", f"node_type={node_type!r}; must be 'world_state'."
    assert node_id == "world", (
        f"patch target node_id={node_id!r}; must be 'world' (DEC-022)."
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
    assert body.get("epoch") == "war", "epoch must be included in the patch payload."
