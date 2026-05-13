"""
scenario_story_pacing.py - Story pacing engine: suppression via active high-severity quest.

Scenario:
  1. Create a Quest node with severity=80 and status=in_progress.
  2. Run one tick advance (story pacing engine fires before event sampling).
  3. Read WorldState via the generic graph endpoint.
  4. Assert max_event_severity <= 30 (suppression cap).
  5. Cleanup.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from conftest import Narrator, api_get, api_post

SCENARIO_ID = "scenario_story_pacing"

QUEST_ID = "sp_quest_high_severity_001"


def test_story_pacing(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    now = datetime.now(timezone.utc).isoformat()
    graph = "/v1/graph"

    try:
        n.narrate("Seed a high-severity in-progress quest so the pacing engine suppresses events.")

        n.step("Create high-severity quest", api_post(http_client, f"{graph}/nodes/Quest", {
            "properties": {
                "id": QUEST_ID,
                "description": "Deliver the princess safely across hostile territory.",
                "quest_giver_id": "sp_unknown_giver",
                "target_id": None,
                "reward_id": None,
                "success_condition": "Reach the castle",
                "failure_condition": None,
                "status": "in_progress",
                "severity": 80,
                "created_at": now,
                "completed_at": None,
            },
        }))

        n.narrate("Advance one tick — the story pacing engine runs before event sampling.")

        advance_resp = api_post(http_client, "/v1/clock/advance", {
            "delta_ticks": 1,
            "game_time_seconds": 60,
        })
        n.step("Advance one tick", advance_resp)

        pacing_results = advance_resp["body"].get("data", {}).get("story_pacing", [])
        if pacing_results:
            first = pacing_results[0]
            assert first["suppressed"] is True, (
                f"Expected pacing engine to suppress events; got suppressed={first.get('suppressed')}"
            )
            assert first["max_event_severity"] <= 30, (
                f"Expected max_event_severity <= 30; got {first.get('max_event_severity')}"
            )

        n.narrate("Read WorldState and assert max_event_severity is at the suppression cap.")

        ws_resp = api_get(http_client, f"{graph}/nodes/WorldState/world")
        n.step("Read WorldState", ws_resp)

        props = ws_resp["body"].get("data", {}).get("properties", {})
        max_sev = props.get("max_event_severity")
        if max_sev is not None:
            assert int(max_sev) <= 30, (
                f"Expected WorldState.max_event_severity <= 30 after pacing suppression; got {max_sev}"
            )

    finally:
        n.save()
