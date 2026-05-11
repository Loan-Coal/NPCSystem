"""
scenario_tavern_secret.py - Gossip propagation via dialogue.

Scenario:
  1. Player tells NPC A a secret at the market.
  2. A gossip tick fires (admin batch endpoint).
  3. Player asks NPC B (same location) if they heard anything.
  4. Transcript shows whether the rumour surfaced in NPC B's response.

No LLM content assertions — manual inspection scenario.
"""

from __future__ import annotations

import httpx

from conftest import Narrator, api_get, api_post

SCENARIO_ID = "scenario_tavern_secret"
NPC_A = "merchant_1"
NPC_B = "guard_1"
PLAYER = "player_1"
LOCATION = "loc_market"


def test_tavern_secret(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)

    try:
        n.narrate(f"Player confides in {NPC_A} at the market.")

        n.step(f"Turn 1 — player tells {NPC_A} the secret", api_post(http_client, "/v1/dialogue", {
            "player_id": PLAYER,
            "npc_id": NPC_A,
            "player_message": "I heard the blacksmith is selling stolen goods.",
            "location_id": LOCATION,
            "session_id": f"{SCENARIO_ID}:turn1",
        }))

        n.narrate("A gossip tick fires. Knowledge may have spread.")

        n.step("Gossip tick (propagation)", api_post(http_client, "/v1/admin/batch/gossip_tick", {
            "tick_override": 1, "max_pairs": 20,
        }))

        n.narrate(f"Player asks {NPC_B} what they've heard.")

        n.step(f"Turn 2 — player asks {NPC_B} about rumours", api_post(http_client, "/v1/dialogue", {
            "player_id": PLAYER,
            "npc_id": NPC_B,
            "player_message": "Have you heard any interesting rumors lately?",
            "location_id": LOCATION,
            "session_id": f"{SCENARIO_ID}:turn2",
        }))

    finally:
        n.save()
