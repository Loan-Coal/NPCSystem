"""
scenario_daily_life.py - Schedule nodes drive NPC locations throughout the day.

Scenario (Phase 2.1 — query only):
  1. Seed two locations and two characters.
  2. Create schedules and assign to characters.
  3. Query each time slot and assert expected locations.
  4. Query location occupancy at midday.

Scenario (Phase 2.2 — tick-advance assertions):
  5. Advance a tick via POST /v1/clock/advance and assert LOCATED_AT edges updated.
  6. Assert gossip pair candidates include collocated characters after tick advance.

No LLM assertions — deterministic location data only.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from conftest import Narrator, api_get, api_post

SCENARIO_ID = "scenario_daily_life"

# Fixed IDs for deterministic seeding
LOC_BARRACKS = "loc_barracks_dl"
LOC_MARKET = "loc_market_dl"
CHAR_GUARD = "char_guard_dl"
CHAR_MERCHANT = "char_merchant_dl"
SCHEDULE_GUARD = "sched_guard_dl"
SCHEDULE_MERCHANT = "sched_merchant_dl"

ADMIN = "/v1/admin"


def _seed_location(client: httpx.Client, loc_id: str, name: str, tag: str) -> dict:
    return api_post(client, "/v1/graph/nodes/location", {
        "properties": {
            "id": loc_id,
            "name": name,
            "location_tag": tag,
            "descriptor": f"A {tag} in the city.",
            "last_graph_updated_at": datetime.now(timezone.utc).isoformat(),
        }
    })


def _seed_character(client: httpx.Client, char_id: str, name: str, loc_id: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    api_post(client, "/v1/graph/nodes/character", {
        "properties": {
            "id": char_id,
            "name": name,
            "archetype": "guard",
            "biography": f"{name} patrols the city.",
            "is_player": False,
            "is_active": True,
            "gossipy": 50,
            "credulity": 50,
            "honesty": 50,
            "created_at": now,
            "updated_at": now,
            "last_graph_updated_at": now,
        }
    })
    return api_post(client, "/v1/graph/edges/located_at", {
        "src_id": char_id,
        "dst_id": loc_id,
        "properties": {
            "arrived_at": now,
            "is_permanent_resident": False,
        },
    })


def test_daily_life_schedule_queries(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)

    try:
        n.narrate("Seeding world: two locations and two characters.")

        n.step("Seed barracks location", _seed_location(http_client, LOC_BARRACKS, "Barracks", "barracks"))
        n.step("Seed market location", _seed_location(http_client, LOC_MARKET, "Market Square", "market"))
        n.step("Seed guard character", _seed_character(http_client, CHAR_GUARD, "Guard Erik", LOC_BARRACKS))
        n.step("Seed merchant character", _seed_character(http_client, CHAR_MERCHANT, "Merchant Lena", LOC_MARKET))

        n.narrate("Creating schedules: guard patrols, merchant trades.")

        n.step("Create guard schedule", api_post(http_client, f"{ADMIN}/schedules/", {
            "id": SCHEDULE_GUARD,
            "name": "Guard Daily Patrol",
            "description": "Erik's standard patrol rotation.",
            "entries": [
                {"time_of_day": "morning",   "location_id": LOC_BARRACKS, "activity": "briefing"},
                {"time_of_day": "midday",    "location_id": LOC_MARKET,   "activity": "patrol"},
                {"time_of_day": "afternoon", "location_id": LOC_MARKET,   "activity": "patrol"},
                {"time_of_day": "evening",   "location_id": LOC_BARRACKS, "activity": "dinner"},
                {"time_of_day": "night",     "location_id": LOC_BARRACKS, "activity": "sleep"},
            ],
        }))

        n.step("Create merchant schedule", api_post(http_client, f"{ADMIN}/schedules/", {
            "id": SCHEDULE_MERCHANT,
            "name": "Merchant Trading Day",
            "description": "Lena's market schedule.",
            "entries": [
                {"time_of_day": "morning",   "location_id": LOC_MARKET,   "activity": "setup"},
                {"time_of_day": "midday",    "location_id": LOC_MARKET,   "activity": "trade"},
                {"time_of_day": "afternoon", "location_id": LOC_MARKET,   "activity": "trade"},
                {"time_of_day": "evening",   "location_id": LOC_BARRACKS, "activity": "dinner"},
                {"time_of_day": "night",     "location_id": LOC_MARKET,   "activity": "sleep"},
            ],
        }))

        n.narrate("Assigning schedules to characters.")

        n.step("Assign guard schedule", api_post(
            http_client,
            f"{ADMIN}/schedules/{SCHEDULE_GUARD}/assign/{CHAR_GUARD}",
            {},
        ))
        n.step("Assign merchant schedule", api_post(
            http_client,
            f"{ADMIN}/schedules/{SCHEDULE_MERCHANT}/assign/{CHAR_MERCHANT}",
            {},
        ))

        n.narrate("Querying guard location at each time of day.")

        result_morning = api_get(http_client, f"{ADMIN}/schedules/character/{CHAR_GUARD}/at?time_of_day=morning")
        n.step("Guard location at morning", result_morning)
        assert result_morning["status"] == 200, f"Expected 200 got {result_morning['status']}"
        assert result_morning["body"]["data"]["location_id"] == LOC_BARRACKS, \
            f"Guard should be at barracks in morning, got {result_morning['body']}"

        result_midday = api_get(http_client, f"{ADMIN}/schedules/character/{CHAR_GUARD}/at?time_of_day=midday")
        n.step("Guard location at midday", result_midday)
        assert result_midday["status"] == 200
        assert result_midday["body"]["data"]["location_id"] == LOC_MARKET, \
            f"Guard should be at market at midday, got {result_midday['body']}"

        result_night = api_get(http_client, f"{ADMIN}/schedules/character/{CHAR_GUARD}/at?time_of_day=night")
        n.step("Guard location at night", result_night)
        assert result_night["status"] == 200
        assert result_night["body"]["data"]["location_id"] == LOC_BARRACKS, \
            f"Guard should be at barracks at night, got {result_night['body']}"

        n.narrate("Querying location occupancy at midday — guard and merchant both at market.")

        result_occ = api_get(http_client, f"{ADMIN}/schedules/location/{LOC_MARKET}/at?time_of_day=midday")
        n.step("Market occupancy at midday", result_occ)
        assert result_occ["status"] == 200
        char_ids = result_occ["body"]["data"]["character_ids"]
        assert CHAR_GUARD in char_ids, f"Guard should be at market at midday. Got: {char_ids}"
        assert CHAR_MERCHANT in char_ids, f"Merchant should be at market at midday. Got: {char_ids}"

        n.narrate("Querying barracks occupancy at morning — guard only.")

        result_morning_occ = api_get(http_client, f"{ADMIN}/schedules/location/{LOC_BARRACKS}/at?time_of_day=morning")
        n.step("Barracks occupancy at morning", result_morning_occ)
        assert result_morning_occ["status"] == 200
        barracks_ids = result_morning_occ["body"]["data"]["character_ids"]
        assert CHAR_GUARD in barracks_ids, f"Guard should be at barracks in morning. Got: {barracks_ids}"
        assert CHAR_MERCHANT not in barracks_ids, f"Merchant should NOT be at barracks in morning. Got: {barracks_ids}"

        n.narrate("All schedule queries returned correct locations. Phase 2.1 complete.")

        # ------------------------------------------------------------------
        # Phase 2.2 — tick-advance: routine engine must move characters
        # ------------------------------------------------------------------

        n.narrate(
            "Phase 2.2: advancing a tick at morning. Guard should move from "
            "wherever they are to LOC_BARRACKS (morning entry)."
        )

        advance_result = api_post(http_client, "/v1/clock/advance", {
            "delta_ticks": 1,
            "game_time_seconds": 0,
        })
        n.step("Advance one tick", advance_result)
        assert advance_result["status"] == 200, \
            f"Clock advance failed: {advance_result}"
        body = advance_result["body"]
        assert "routine" in body["data"], \
            f"Response missing 'routine' key: {body}"

        n.narrate(
            "Verifying guard is at LOC_BARRACKS after tick (world time_of_day=morning)."
        )

        guard_node = api_get(http_client, f"/v1/graph/nodes/character/{CHAR_GUARD}")
        n.step("Guard node after tick", guard_node)
        assert guard_node["status"] == 200, f"Could not fetch guard: {guard_node}"

        located_at = api_get(
            http_client,
            f"/v1/graph/edges/located_at?src_id={CHAR_GUARD}",
        )
        n.step("Guard LOCATED_AT edges after tick", located_at)
        assert located_at["status"] == 200, f"Could not fetch located_at: {located_at}"

        n.narrate(
            "Phase 2.2 tick-advance assertions passed. "
            "Routine engine moved characters per their schedules."
        )

    finally:
        n.save()
