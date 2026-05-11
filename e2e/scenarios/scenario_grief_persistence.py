"""
scenario_grief_persistence.py - Emotion persistence across dialogue turns.

Scenario:
  1. Player delivers bad news to an elder NPC.
  2. NPC emotion state is read immediately after.
  3. Player returns and continues the conversation.
  4. Transcript shows whether the NPC's tone reflects the prior grief.

No LLM content assertions — manual inspection scenario.
"""

from __future__ import annotations

import httpx

from conftest import Narrator, api_get, api_post

SCENARIO_ID = "scenario_grief_persistence"
NPC = "elder_1"
PLAYER = "player_1"
LOCATION = "loc_market"


def test_grief_persistence(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    session_id = f"{SCENARIO_ID}:{PLAYER}:{NPC}"

    try:
        n.narrate("Player brings terrible news to the elder.")

        n.step("Turn 1 — delivering grief", api_post(http_client, "/v1/dialogue", {
            "player_id": PLAYER,
            "npc_id": NPC,
            "player_message": "Elder, my daughter passed away last night. She was only seven.",
            "location_id": LOCATION,
            "session_id": session_id,
        }))

        n.step("NPC emotion after turn 1", api_get(http_client, f"/v1/npc/{NPC}/emotion"))
        n.step("NPC state after turn 1", api_get(http_client, f"/v1/npc/{NPC}/state"))

        n.narrate("Player returns. Will the elder still carry the grief?")

        n.step("Turn 2 — follow-up (emotion should persist)", api_post(http_client, "/v1/dialogue", {
            "player_id": PLAYER,
            "npc_id": NPC,
            "player_message": "I came back to talk. I still feel so lost.",
            "location_id": LOCATION,
            "session_id": session_id,
        }))

        n.step("NPC emotion after turn 2", api_get(http_client, f"/v1/npc/{NPC}/emotion"))

    finally:
        n.save()
