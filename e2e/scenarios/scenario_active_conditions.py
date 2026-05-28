"""
Module: scenario_active_conditions
Layer: e2e
Purpose: Verify that generic active_conditions on WorldState (R2.2) shape NPC dialogue
         for any condition — not just epoch=war. Tests with crop_blight from the village world.
Dependencies: e2e.scenarios.conftest
Used by: make scenarios (--scenarios-only flag)

Requirements:
  - Running NPC Engine API (docker-compose up -d)
  - Village world seeded: make seed-village-world
  - WorldState active_conditions includes "crop_blight"
  - NPCs: vw_elder (village square), vw_healer (healer's hut)
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from e2e.scenarios.conftest import api_get, api_post

# NPCs in the village world who have knowledge of the blight
_VW_ELDER = "vw_elder"
_VW_HEALER = "vw_healer"


def _require_crop_blight(http_client: httpx.Client) -> None:
    """Skip test if world_state does not have crop_blight in active_conditions.

    The village and demo worlds share world_state id='world'. If demo-seed ran
    last, it overwrites active_conditions with northern_war. Re-run
    `make seed-village-world` (last) to restore crop_blight.
    """
    ws = api_get(http_client, "/v1/graph/nodes/world_state/world")
    if ws["status"] != 200:
        pytest.skip("world_state/world not found — seed a world first")
    conditions: list = ws["body"].get("data", {}).get("active_conditions", [])
    if "crop_blight" not in conditions:
        pytest.skip(
            f"world_state.active_conditions={conditions!r} — crop_blight not active. "
            "Run: make seed-village-world (must run after make demo-seed)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test 1 — vw_elder acknowledges crop_blight from active_conditions
# ══════════════════════════════════════════════════════════════════════════════


def test_npc_acknowledges_active_condition_blight(
    http_client: httpx.Client,
) -> None:
    """vw_elder references blight/crops when asked how the village is doing.

    The village world seeds WorldState {active_conditions: ["crop_blight"]}.
    Rule 1 (WORLD STATE) in system_v1.yaml must cause the NPC to acknowledge
    active_conditions, not just epoch. This test verifies the generalisation
    added in R2.2 works for a non-war condition.

    Requires village world: make seed-village-world
    """
    _require_crop_blight(http_client)
    result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_eval",
            "npc_id": _VW_ELDER,
            "player_message": "How are things in the village lately?",
            "session_id": f"active_cond_elder_{uuid.uuid4().hex[:8]}",
        },
    )

    if result["status"] == 404:
        pytest.skip(
            f"NPC {_VW_ELDER!r} not found — village world not seeded. "
            "Run: make seed-village-world"
        )

    assert result["status"] == 200, f"Dialogue failed: {result}"
    npc_response = (result["body"].get("npc_response") or "").lower()
    assert npc_response, "Empty NPC response — check that the LLM stack is running."
    print(f"\n[vw_elder]\n  {npc_response}\n")

    blight_keywords = ["blight", "crop", "harvest", "field", "famine", "disease", "rot", "grain"]
    matched = [kw for kw in blight_keywords if kw in npc_response]
    assert matched, (
        f"vw_elder did not acknowledge active_condition 'crop_blight'. "
        f"Expected at least one of {blight_keywords!r} in response.\n"
        f"Response: {npc_response!r}"
    )
    print(f"  matched keywords: {matched}")


# ══════════════════════════════════════════════════════════════════════════════
# Test 2 — vw_healer also acknowledges blight (different NPC, same world state)
# ══════════════════════════════════════════════════════════════════════════════


def test_multiple_npcs_share_active_condition_awareness(
    http_client: httpx.Client,
) -> None:
    """vw_healer also acknowledges crop_blight — world state is shared across NPCs.

    Verifies that the active_conditions anchoring from Rule 1 applies to any NPC,
    not just NPCs with direct KNOWS_ABOUT edges to blight-related events.

    Requires village world: make seed-village-world
    """
    _require_crop_blight(http_client)
    result = api_post(
        http_client,
        "/v1/dialogue",
        {
            "player_id": "player_eval",
            "npc_id": _VW_HEALER,
            "player_message": "Are people in the village doing well?",
            "session_id": f"active_cond_healer_{uuid.uuid4().hex[:8]}",
        },
    )

    if result["status"] == 404:
        pytest.skip(
            f"NPC {_VW_HEALER!r} not found — village world not seeded. "
            "Run: make seed-village-world"
        )

    assert result["status"] == 200, f"Dialogue failed: {result}"
    npc_response = (result["body"].get("npc_response") or "").lower()
    assert npc_response, "Empty NPC response — check that the LLM stack is running."
    print(f"\n[vw_healer]\n  {npc_response}\n")

    concern_keywords = [
        "blight", "crop", "harvest", "hunger", "sick", "ill", "disease",
        "worry", "concern", "difficult", "shortage", "struggle",
    ]
    matched = [kw for kw in concern_keywords if kw in npc_response]
    assert matched, (
        f"vw_healer did not acknowledge crop_blight or its downstream effects. "
        f"Expected concern/blight reference from {concern_keywords!r}.\n"
        f"Response: {npc_response!r}"
    )
    print(f"  matched keywords: {matched}")
