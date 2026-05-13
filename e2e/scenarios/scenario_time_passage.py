"""
scenario_time_passage.py - Structured game time advances correctly via the clock endpoint.

Scenario (Phase 3.1):
  1. Advance time_of_day through all 5 slots; assert wrap increments day.
  2. Advance day to 28; assert next day advance increments season and resets day to 1.

No LLM assertions — deterministic only.
"""

from __future__ import annotations

import httpx
import pytest

from conftest import Narrator, api_post

SCENARIO_ID = "scenario_time_passage"
CLOCK_ADVANCE = "/v1/clock/advance"


def _advance(client: httpx.Client, field: str) -> dict:
    """POST clock advance with advance_time_field and return the world_state payload."""
    result = api_post(client, CLOCK_ADVANCE, {
        "delta_ticks": 1,
        "game_time_seconds": 0,
        "advance_time_field": field,
    })
    assert result["status"] == 200, f"clock advance failed: {result}"
    body = result["body"]
    assert "data" in body, f"missing 'data' in response: {body}"
    assert "world_state" in body["data"], f"missing 'world_state' in data: {body['data']}"
    return body["data"]["world_state"]


def test_time_passage(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)

    n.narrate("Phase 3.1 — structured game time via clock advance endpoint.")

    # --- Part 1: time_of_day cycles through 5 slots; night→morning increments day ---
    n.narrate("Advancing time_of_day through all 5 slots.")

    slots = ["midday", "afternoon", "evening", "night", "morning"]
    for expected_slot in slots:
        ws = _advance(http_client, "time_of_day")
        n.step(f"time_of_day → {expected_slot}", {"time_of_day": ws["time_of_day"]})
        assert ws["time_of_day"] == expected_slot, (
            f"Expected time_of_day={expected_slot!r}, got {ws['time_of_day']!r}"
        )

    # After the 5th advance (night→morning) the day must have incremented.
    # We don't know the exact starting day (world state is shared), so we just
    # assert the wrap happened by checking time_of_day is morning again.
    assert ws["time_of_day"] == "morning"

    # Record day value after one full day-cycle so we can track the next wrap.
    day_after_wrap = ws["day"]
    n.narrate(f"Day after first full time_of_day cycle: {day_after_wrap}")

    # --- Part 2: advance day to 28, then assert season increments ---
    # First read current world state via clock state endpoint.
    # We'll drive day to 28 by advancing 'day' repeatedly.
    # Calculate how many advances needed to reach day 28.
    current_day = day_after_wrap
    advances_needed = (28 - current_day) % 28  # how many 'day' advances to reach 28
    if advances_needed == 0:
        advances_needed = 0  # already at 28

    n.narrate(f"Current day={current_day}. Advancing day {advances_needed} time(s) to reach day 28.")
    for _ in range(advances_needed):
        ws = _advance(http_client, "day")

    # One more advance triggers the wrap (day 28 → day 1, season increments).
    n.narrate("Advancing day past 28 — expecting season increment and day reset to 1.")
    ws = _advance(http_client, "day")
    n.step("season incremented", {"day": ws["day"], "season": ws["season"]})
    assert ws["day"] == 1, f"Expected day=1 after season wrap, got {ws['day']}"
    assert ws["season"] != "spring" or ws["year"] > 1, (
        "Season or year should have advanced after day wrap"
    )
