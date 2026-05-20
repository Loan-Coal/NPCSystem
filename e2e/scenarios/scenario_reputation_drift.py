"""
scenario_reputation_drift.py - Reputation arithmetic and clamping.

Scenario:
  1. Create a faction, NPC member, and player character.
  2. Set player reputation with the faction to 60 (friendly).
  3. Adjust reputation down by 90 — should clamp to -30.
  4. Verify final standing via GET endpoint.

No LLM content assertions — data-plane correctness scenario.

Note (ISSUE-005): Event-triggered reputation adjustment (adjust_reputation_for_event
wired in EventHandler.run_tick) is validated at unit level in
tests/unit/test_event_reputation_wiring.py. E2E coverage would require forcing a
specific event template (non-trivial with random selection), so unit tests are
the authoritative coverage for that path.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from conftest import Narrator, api_get, api_post, api_put, char_props

SCENARIO_ID = "scenario_reputation_drift"

FACTION_ID = "rep_test_faction"
NPC_ID = "rep_test_npc"
PLAYER_ID = "rep_test_player"


def test_reputation_drift(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    now = datetime.now(timezone.utc).isoformat()
    admin = "/v1/admin"
    graph = "/v1/graph"

    try:
        n.narrate("Setting up faction and characters.")

        n.step("Create faction", api_post(http_client, f"{admin}/factions/", {
            "id": FACTION_ID, "name": "Test Faction", "archetype": "political", "is_active": True,
        }))
        n.step("Create NPC", api_post(http_client, f"{graph}/nodes/Character", {
            "properties": char_props(NPC_ID, "NPC", is_player=False, now=now),
        }))
        n.step("NPC joins faction", api_post(http_client, f"{admin}/factions/{FACTION_ID}/members", {
            "character_id": NPC_ID, "role": "member", "status": "active",
        }))
        n.step("Create player", api_post(http_client, f"{graph}/nodes/Character", {
            "properties": char_props(PLAYER_ID, "Player", is_player=True, now=now),
        }))

        n.narrate("Player starts friendly (60). A major incident drops standing by 90.")

        n.step("Set reputation +60 (friendly)", api_put(http_client,
            f"{admin}/characters/{PLAYER_ID}/reputation/{FACTION_ID}", {"standing": 60}))
        n.step("Read reputation before adjust", api_get(http_client,
            f"{graph}/characters/{PLAYER_ID}/reputation/{FACTION_ID}"))
        n.step("Adjust -90 (should clamp to -30)", api_post(http_client,
            f"{admin}/characters/{PLAYER_ID}/reputation/{FACTION_ID}/adjust", {"delta": -90}))

        final = api_get(http_client, f"{graph}/characters/{PLAYER_ID}/reputation/{FACTION_ID}")
        n.step("Final reputation (expect -30)", final)

        assert final["body"]["data"]["standing"] == -30, (
            f"Expected -30, got {final['body']['data']['standing']}"
        )

    finally:
        n.save()
