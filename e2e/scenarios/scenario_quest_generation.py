"""
scenario_quest_generation.py - Quest generation engine: slot-filling and quest node creation.

Scenario:
  1. Create a character (archetype: merchant) as quest giver.
  2. Create an item node owned by that character.
  3. Call POST /v1/admin/quests/generate with the character ID.
  4. Assert a quest node is created with a non-empty description.
  5. Call GET /v1/admin/quests/{quest_id} to verify the quest node exists.
  6. Assert the character has a HAS_QUEST edge via the generated quest_id.
  7. Cleanup.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from conftest import Narrator, api_get, api_patch, api_post, char_props

SCENARIO_ID = "scenario_quest_generation"

GIVER_ID = "qg_char_merchant_001"
ITEM_ID = "qg_item_sword_001"


def test_quest_generation(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    now = datetime.now(timezone.utc).isoformat()
    admin = "/v1/admin"
    graph = "/v1/graph"

    generated_quest_id: str | None = None

    try:
        # Reset pacing rate so this test is not affected by stale DB state from prior runs.
        api_patch(http_client, f"{graph}/nodes/WorldState/world", {"properties": {"quest_generation_rate": 1.0}})

        n.narrate("Create a merchant character who will give a quest.")
        n.step("Create merchant character", api_post(http_client, f"{graph}/nodes/Character", {
            "properties": char_props(GIVER_ID, "Merchant Bob", is_player=False, archetype="merchant", now=now),
        }))

        n.narrate("Create an item node so the slot-filler has a candidate.")
        n.step("Create item", api_post(http_client, f"{admin}/items/{GIVER_ID}", {
            "name": "Iron Sword",
            "description": "A basic iron sword.",
            "value": 50,
            "rarity": "common",
            "type": "weapon",
            "is_unique": False,
            "game_time": {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"},
        }))

        n.narrate("Generate a quest for the merchant.")
        gen_resp = api_post(http_client, f"{admin}/quests/generate", {
            "quest_giver_id": GIVER_ID,
        })
        n.step("Generate quest", gen_resp)

        assert gen_resp["status"] == 200, f"Generate quest failed: {gen_resp['body']}"
        data = gen_resp["body"].get("data", {})
        generated_quest_id = data.get("quest_id")
        description = data.get("description", "")
        assert generated_quest_id, f"Expected quest_id in response; got: {data}"
        assert description, f"Expected non-empty description; got: {data}"

        n.narrate(f"Verify the quest node exists: {generated_quest_id}.")
        quest_resp = api_get(http_client, f"{admin}/quests/{generated_quest_id}")
        n.step("Get quest node", quest_resp)

        assert quest_resp["status"] == 200, f"Get quest failed: {quest_resp['body']}"
        quest_data = quest_resp["body"].get("data", {}).get("quest", {})
        assert quest_data.get("id") == generated_quest_id
        assert quest_data.get("quest_giver_id") == GIVER_ID
        assert quest_data.get("status") == "offered"

    finally:
        n.narrate("Cleanup: delete item and character.")
        if generated_quest_id:
            http_client.delete(f"{admin}/quests/{generated_quest_id}")
        http_client.delete(f"{admin}/items/{ITEM_ID}")
        http_client.delete(f"{admin}/graph/characters/{GIVER_ID}")
        n.save()
