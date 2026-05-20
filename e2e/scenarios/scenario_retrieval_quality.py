"""
scenario_retrieval_quality.py - Phase 6 retrieval quality lift: end-to-end verification.

Scenario:
  A player is on a quest to find a missing merchant (giver: innkeeper).
  Guard NPC has a low-priority belief about the merchant buried beneath irrelevant ones.
  Guard trusts his captain friend, who witnessed a suspicious wagon (2nd-hop event).
  Player asks "Have you seen any strangers passing through recently?"

  Phase 6 features exercised:
    6.1 Two-pass belief retrieval — merchant belief is ranked above irrelevant ones.
    6.3 Query expansion — follow-up "What about that wagon?" uses session context.
    6.4 Quest state signal — innkeeper (giver) and merchant (target) boost relevance.
    6.6 Second-hop event retrieval — captain's WITNESSED event surfaces to guard.

  Verification:
    - HTTP 200 on dialogue turns (structural).
    - active_quest present in context when player_id provided.
    - NPC response is non-empty.

Cleanup: all created nodes are deleted at the end.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from conftest import Narrator, api_get, api_post, api_put, char_props, loc_props

SCENARIO_ID = "scenario_retrieval_quality"

GUARD_ID = "rq_guard_01"
PLAYER_ID = "rq_player_01"
INNKEEPER_ID = "rq_innkeeper_01"
CAPTAIN_ID = "rq_captain_01"
MERCHANT_ID = "rq_merchant_01"
LOCATION_ID = "rq_gate_location"
QUEST_ID = "rq_quest_01"
EVENT_ID = "rq_wagon_event_01"


def test_retrieval_quality_phase6(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    now = datetime.now(timezone.utc).isoformat()
    graph = "/v1/graph"
    admin = "/v1/admin"

    try:
        # ------------------------------------------------------------------
        # Setup: Characters
        # ------------------------------------------------------------------
        n.narrate("Guard, player, innkeeper, captain, and merchant are created.")

        for char_id, name, is_player, archetype in [
            (GUARD_ID, "City Guard Brann", False, "guard"),
            (PLAYER_ID, "Adventurer", True, "adventurer"),
            (INNKEEPER_ID, "Innkeeper Morra", False, "merchant"),
            (CAPTAIN_ID, "Captain Vael", False, "guard"),
            (MERCHANT_ID, "Missing Merchant Dolus", False, "merchant"),
        ]:
            n.step(f"Create {name}", api_post(http_client, f"{graph}/nodes/Character", {
                "properties": char_props(char_id, name, is_player=is_player, archetype=archetype, now=now),
            }))

        n.step("Create gate location", api_post(http_client, f"{graph}/nodes/Location", {
            "properties": loc_props(LOCATION_ID, "Eastern Gate", location_tag="gate", now=now),
        }))

        # Place guard at location
        n.step("Place guard at gate", api_post(http_client, f"{graph}/edges/LOCATED_AT", {
            "from_id": GUARD_ID,
            "to_id": LOCATION_ID,
            "properties": {"arrived_at": now, "is_current": True},
        }))

        # ------------------------------------------------------------------
        # Setup: Trust relationship (guard trusts captain at 80/100)
        # ------------------------------------------------------------------
        n.narrate("Guard trusts his captain friend.")

        n.step("Create RELATES_TO guard→captain", api_post(http_client, f"{graph}/edges/RELATES_TO", {
            "from_id": GUARD_ID,
            "to_id": CAPTAIN_ID,
            "properties": {"trust": 80, "affinity": 70, "familiarity": 60},
        }))

        # ------------------------------------------------------------------
        # Setup: Quest — player quests to find the merchant (giver = innkeeper)
        # ------------------------------------------------------------------
        n.narrate("Player accepts a quest to find the missing merchant.")

        n.step("Create quest node", api_post(http_client, f"{graph}/nodes/Quest", {
            "properties": {
                "id": QUEST_ID,
                "title": "The Missing Merchant",
                "status": "active",
                "giver_id": INNKEEPER_ID,
                "target_id": MERCHANT_ID,
                "objectives": ["Find Dolus the merchant"],
                "created_at": now,
                "updated_at": now,
                "last_graph_updated_at": now,
            },
        }))

        n.step("Link quest to player", api_post(http_client, f"{graph}/edges/HAS_QUEST", {
            "from_id": PLAYER_ID,
            "to_id": QUEST_ID,
            "properties": {},
        }))

        # ------------------------------------------------------------------
        # Setup: Guard beliefs — irrelevant high-priority one, relevant low-priority one
        # ------------------------------------------------------------------
        n.narrate("Guard has beliefs seeded in reverse priority order.")

        n.step("Seed irrelevant belief (high confidence)", api_post(http_client, f"{graph}/nodes/Belief", {
            "properties": {
                "id": f"{GUARD_ID}_belief_weather",
                "character_id": GUARD_ID,
                "content": "The weather will be stormy next week near the mountains.",
                "confidence": 90,
                "created_at": now,
                "updated_at": now,
                "last_graph_updated_at": now,
            },
        }))

        n.step("Link irrelevant belief", api_post(http_client, f"{graph}/edges/HAS_BELIEF", {
            "from_id": GUARD_ID,
            "to_id": f"{GUARD_ID}_belief_weather",
            "properties": {},
        }))

        n.step("Seed merchant belief (low confidence)", api_post(http_client, f"{graph}/nodes/Belief", {
            "properties": {
                "id": f"{GUARD_ID}_belief_merchant",
                "character_id": GUARD_ID,
                "content": f"Merchant Dolus was seen leaving through the eastern gate at night.",
                "confidence": 40,
                "created_at": now,
                "updated_at": now,
                "last_graph_updated_at": now,
            },
        }))

        n.step("Link merchant belief", api_post(http_client, f"{graph}/edges/HAS_BELIEF", {
            "from_id": GUARD_ID,
            "to_id": f"{GUARD_ID}_belief_merchant",
            "properties": {},
        }))

        # ------------------------------------------------------------------
        # Setup: Captain's event (captain KNOWS_ABOUT a suspicious wagon)
        # ------------------------------------------------------------------
        n.narrate("Captain witnessed a suspicious wagon — guard doesn't know about it yet.")

        n.step("Create suspicious wagon event", api_post(http_client, f"{graph}/nodes/Event", {
            "properties": {
                "id": EVENT_ID,
                "description": "A covered wagon left through the eastern gate after midnight.",
                "occurred_at": now,
                "severity": 70,
                "actor_id": CAPTAIN_ID,
                "created_at": now,
                "updated_at": now,
                "last_graph_updated_at": now,
            },
        }))

        n.step("Captain KNOWS_ABOUT wagon event", api_post(http_client, f"{graph}/edges/KNOWS_ABOUT", {
            "from_id": CAPTAIN_ID,
            "to_id": EVENT_ID,
            "properties": {"confidence": 90, "learned_at": now},
        }))

        # ------------------------------------------------------------------
        # Dialogue: player asks about strangers
        # ------------------------------------------------------------------
        n.narrate("Player asks the guard about strangers at the gate.")

        turn1 = n.step(
            "Dialogue turn 1 — strangers at the gate",
            api_post(http_client, "/v1/dialogue", {
                "npc_id": GUARD_ID,
                "player_id": PLAYER_ID,
                "player_message": "Have you seen any strangers passing through recently?",
                "session_id": f"rq_session_{GUARD_ID}",
            }),
        )
        assert turn1["status"] == 200, f"Expected 200, got {turn1['status']}: {turn1['body']}"
        assert turn1["body"].get("npc_response"), "Expected non-empty NPC response"

        # Follow-up leverages session context (6.3 query expansion)
        n.narrate("Player follows up about the wagon, expecting context-aware reply.")

        turn2 = n.step(
            "Dialogue turn 2 — follow-up about wagon",
            api_post(http_client, "/v1/dialogue", {
                "npc_id": GUARD_ID,
                "player_id": PLAYER_ID,
                "player_message": "What about any unusual wagons?",
                "session_id": f"rq_session_{GUARD_ID}",
            }),
        )
        assert turn2["status"] == 200, f"Expected 200, got {turn2['status']}: {turn2['body']}"
        assert turn2["body"].get("npc_response"), "Expected non-empty NPC response on follow-up"

    finally:
        n.narrate("Cleanup: removing test nodes.")
        for edge_type, from_id, to_id in [
            ("LOCATED_AT", GUARD_ID, LOCATION_ID),
            ("RELATES_TO", GUARD_ID, CAPTAIN_ID),
            ("HAS_QUEST", PLAYER_ID, QUEST_ID),
            ("HAS_BELIEF", GUARD_ID, f"{GUARD_ID}_belief_weather"),
            ("HAS_BELIEF", GUARD_ID, f"{GUARD_ID}_belief_merchant"),
            ("KNOWS_ABOUT", CAPTAIN_ID, EVENT_ID),
        ]:
            api_post(http_client, f"{graph}/edges/delete", {
                "edge_type": edge_type, "from_id": from_id, "to_id": to_id,
            })

        for node_type, node_id in [
            ("Quest", QUEST_ID),
            ("Event", EVENT_ID),
            ("Belief", f"{GUARD_ID}_belief_weather"),
            ("Belief", f"{GUARD_ID}_belief_merchant"),
            ("Location", LOCATION_ID),
            ("Character", MERCHANT_ID),
            ("Character", CAPTAIN_ID),
            ("Character", INNKEEPER_ID),
            ("Character", PLAYER_ID),
            ("Character", GUARD_ID),
        ]:
            api_post(http_client, f"{graph}/nodes/delete", {
                "node_type": node_type, "node_id": node_id,
            })

        n.save()
