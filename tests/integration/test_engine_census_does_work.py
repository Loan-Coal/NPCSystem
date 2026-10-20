"""
Module: test_engine_census_does_work
Layer: test (integration)
Purpose: Assert that every tick engine expected to produce work does so
    against the seeded demo world, using working_set_size from
    GET /v1/admin/system/engines (added by T15.1) as the observable.

RED anchor (against the tree before T5.1, commit 66dcc8d1):
    On that stack, FOLLOWS_SCHEDULE and HAS_NEED edges are absent, so
    routine returns moved=0+skipped=0 and need_decay returns needs_updated=0,
    both mapping to working_set_size=0.  Additionally, the working_set_size
    field itself does not exist on pre-T15.1 stacks, so it is absent from
    the /engines response (treated as None = no work done here).
    Both assertions in _EXPECTED_WORKING therefore fail on that tree — the
    intended red.

On the current tree (post-T5.1 + T5.2 + T15.1):
    routine.working_set_size > 0  (FOLLOWS_SCHEDULE seeded by T5.1)
    need_decay.working_set_size > 0  (HAS_NEED seeded by T5.2)

Does NOT: run without the eval stack; seed the world (run ``make eval-stack-seed``).
Does: advance _ADVANCE_TICKS ticks cycling time_of_day, then reads
    GET /v1/admin/system/engines and asserts _EXPECTED_WORKING engines worked.
    Logs _LEGITIMATELY_IDLE engine status informally without asserting.

Reproducing failure on pre-Sprint-3:
    bash scripts/eval_stack_at.sh 66dcc8d1 --reset
    make eval-stack-seed
    pytest tests/integration/test_engine_census_does_work.py -v
    # expect FAILED on routine and need_decay

Dependencies: httpx (HTTP clock advance, engines read),
    neo4j async driver (seed check, clock pin).
Used by: T15.2 validation (eval stack only, not make test-integration).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
import pytest
from neo4j import AsyncGraphDatabase

_LOGGER = logging.getLogger(__name__)

_EVAL_BASE_URL: str = os.getenv("EVAL_BASE_URL", "http://localhost:8001")
_EVAL_NEO4J_URI: str = os.getenv("EVAL_NEO4J_URI", "bolt://localhost:7688")
_EVAL_NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
_EVAL_NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
_EVAL_WORLD_ID: str = os.getenv("EVAL_WORLD_ID", "world")

_PINNED_TIME_OF_DAY: str = "morning"

# 12 ticks: covers two full time_of_day cycles so routine relocates every NPC
# at least twice, and includes gossip's 10-tick firing window.
_ADVANCE_TICKS: int = 12

_CYPHER_COUNT_SCHEDULE_EDGES = "MATCH ()-[r:FOLLOWS_SCHEDULE]->() RETURN count(r) AS n"
_CYPHER_COUNT_HAS_NEED_EDGES = "MATCH ()-[r:HAS_NEED]->() RETURN count(r) AS n"
_CYPHER_PIN_CLOCK = (
    "MATCH (w:WorldState {id: $world_id}) "
    "SET w.time_of_day = $slot "
    "RETURN count(w) AS n"
)

# Engines that MUST have working_set_size > 0 after _ADVANCE_TICKS ticks against
# the seeded demo world.  A zero (or absent) working_set_size fails the test.
#
# These two were the hard failures at Sprint 2/3 review: 27 engines ran, only 6
# did work, and these two were permanently returning zero because T5.1/T5.2 had
# not yet seeded the edges they depend on.
_EXPECTED_WORKING: dict[str, str] = {
    "routine": (
        "moves NPCs via FOLLOWS_SCHEDULE edges seeded by T5.1; "
        "returned moved=0+skipped=0 before T5.1 (pre-Sprint-3 regression)"
    ),
    "need_decay": (
        "decays HAS_NEED level each tick and applies location-based restoration "
        "(seeded by T5.2); returned needs_updated=0 before T5.2"
    ),
}

# Engines not expected to produce non-zero working_set_size with the demo seed in
# a _ADVANCE_TICKS-tick run.  Listed explicitly so silent omissions are visible
# on inspection — an unlisted engine registering here is a surprise worth reviewing.
_LEGITIMATELY_IDLE: dict[str, str] = {
    "story_pacing": (
        "working_set_size = max_event_severity (int); 0 in early game with no "
        "active high-severity quests"
    ),
    "gossip": (
        "interval-gated every 10 ticks; pairs depend on current co-location "
        "density which varies with routine movement history across test runs"
    ),
    "event": (
        "interval-gated every 20 ticks; does not fire within a 12-tick window "
        "from an arbitrary starting tick"
    ),
    "chapter": "LLM + interval-gated; rarely produces output in a short run",
    "agenda": "no active agenda items in the demo seed",
    "event_quest": (
        "triggers on unprocessed Event nodes without CAUSED_BY; depends on the "
        "event engine having fired at least once first"
    ),
    "need_quest": (
        "triggers on Need.level below threshold; needs several decay ticks "
        "to cross the threshold from the seeded start level (~15-85)"
    ),
    "world_state_quest": (
        "triggers on WorldState epoch conditions rarely met in a fresh seed"
    ),
    "proactive_dialogue": (
        "returns proactive_lines list (not an int); "
        "working_set_size=0 by _derive_working_set_size design"
    ),
    "reputation": (
        "nudges RELATES_TO trust on gossip propagation; "
        "0 without a prior gossip trust delta in this run"
    ),
    "intent_formation": (
        "forms intents from active agenda items; 0 without active agendas"
    ),
    "goal_formation": (
        "returns goal_formations list (not an int); "
        "working_set_size=0 by _derive_working_set_size design"
    ),
    "player_model": (
        "updates player model on NPC co-location with player; "
        "0 without player NPC in proximity after routine movement"
    ),
    "director": (
        "director_beats count; 0 without active storylines in the demo seed"
    ),
    "memory_decay": "decays Memory nodes; 0 with no memories seeded in demo",
    "scheme_advance": "advances active schemes; 0 with no schemes seeded",
    "scheme_detection": "detects covert scheme steps; 0 with no schemes seeded",
    "memory_consolidation": (
        "LLM + advance-cadence (not per-tick); does not run in a "
        "12-tick, 0-day-advance run"
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_api_key() -> str:
    """Return the eval-stack API key, defaulting to the dev secret.

    Uses EVAL_API_KEY (not API_KEY_SECRET) to avoid picking up the
    test-collection stub that conftest.py seeds via setdefault.

    Returns:
        Bearer token string.
    """
    return os.getenv("EVAL_API_KEY", "local_dev_secret_change_this_2026")


def _auth_headers() -> dict[str, str]:
    """Return the Authorization header dict for eval-stack API calls.

    Returns:
        Dict with Authorization Bearer token.
    """
    return {"Authorization": f"Bearer {_read_api_key()}"}


def _skip_if_no_eval_stack() -> None:
    """Skip the test if the eval stack is not reachable at _EVAL_BASE_URL."""
    try:
        r = httpx.get(f"{_EVAL_BASE_URL}/health", timeout=5.0)
        r.raise_for_status()
    except Exception as exc:
        pytest.skip(f"eval stack not reachable at {_EVAL_BASE_URL}: {exc}")


async def _check_seed_or_skip() -> None:
    """Skip if the demo world has not been seeded (no FOLLOWS_SCHEDULE or HAS_NEED edges).

    Both edge types are prerequisites for the two asserted engines.  Running
    ``make eval-stack-seed`` creates them.
    """
    driver = AsyncGraphDatabase.driver(
        _EVAL_NEO4J_URI, auth=(_EVAL_NEO4J_USER, _EVAL_NEO4J_PASSWORD)
    )
    try:
        async with driver.session() as session:
            sched = await (await session.run(_CYPHER_COUNT_SCHEDULE_EDGES)).single()
            if sched is None or sched["n"] == 0:
                pytest.skip(
                    "no FOLLOWS_SCHEDULE edges: run `make eval-stack-seed` first"
                )
            needs = await (await session.run(_CYPHER_COUNT_HAS_NEED_EDGES)).single()
            if needs is None or needs["n"] == 0:
                pytest.skip(
                    "no HAS_NEED edges: run `make eval-stack-seed` first"
                )
    finally:
        await driver.close()


async def _pin_clock_or_skip() -> None:
    """Reset WorldState.time_of_day to _PINNED_TIME_OF_DAY, or skip if unseeded.

    Pinning to "morning" guarantees mira_innkeeper's schedule target (market_square)
    differs from her start location (tavern), ensuring routine.moved >= 1 on tick 1.
    Without this, a prior test run might leave the clock at a slot where all NPCs
    are already at their scheduled locations and routine.moved == 0.
    """
    driver = AsyncGraphDatabase.driver(
        _EVAL_NEO4J_URI, auth=(_EVAL_NEO4J_USER, _EVAL_NEO4J_PASSWORD)
    )
    try:
        async with driver.session() as session:
            pinned = await (
                await session.run(
                    _CYPHER_PIN_CLOCK,
                    world_id=_EVAL_WORLD_ID,
                    slot=_PINNED_TIME_OF_DAY,
                )
            ).single()
            if pinned is None or pinned["n"] == 0:
                pytest.skip(
                    f"no WorldState node with id={_EVAL_WORLD_ID!r}: "
                    "run `make eval-stack-seed` first"
                )
    finally:
        await driver.close()


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_census_working_set() -> None:
    """Every engine in _EXPECTED_WORKING has working_set_size > 0 after _ADVANCE_TICKS ticks.

    Advances the clock _ADVANCE_TICKS times against the seeded demo world, cycling
    time_of_day so routine moves NPCs across every scheduled slot.  After the
    advances, reads GET /v1/admin/system/engines and asserts each engine in
    _EXPECTED_WORKING has a non-zero working_set_size.

    Informally logs _LEGITIMATELY_IDLE engines and flags any uncatalogued engine
    that appeared in the response (unexpected engine names are worth reviewing).

    Against the pre-Sprint-3 tree (66dcc8d1): both asserted engines have
    working_set_size=None (field absent) or 0, so the test fails — the intended red.
    """
    _skip_if_no_eval_stack()
    await _check_seed_or_skip()
    await _pin_clock_or_skip()

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(_ADVANCE_TICKS):
            payload: dict[str, Any] = {"delta_ticks": 1, "game_time_seconds": 1}
            if i > 0:
                payload["advance_time_field"] = "time_of_day"
            resp = await client.post(
                f"{_EVAL_BASE_URL}/v1/clock/advance",
                json=payload,
                headers=_auth_headers(),
            )
            resp.raise_for_status()
            _LOGGER.debug("advance %d/%d: %s", i + 1, _ADVANCE_TICKS, resp.status_code)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_EVAL_BASE_URL}/v1/admin/system/engines",
            headers=_auth_headers(),
        )
        resp.raise_for_status()

    records: dict[str, Any] = {
        rec["engine_name"]: rec for rec in resp.json()["data"]
    }

    failures: list[str] = []
    for engine_name, reason in _EXPECTED_WORKING.items():
        record = records.get(engine_name)
        if record is None:
            failures.append(
                f"{engine_name}: absent from /v1/admin/system/engines "
                "(engine never registered)"
            )
            continue
        wss = record.get("working_set_size")
        if wss is None or wss <= 0:
            failures.append(
                f"{engine_name}: working_set_size={wss!r} (expected > 0) — {reason}"
            )

    for engine_name, reason in _LEGITIMATELY_IDLE.items():
        record = records.get(engine_name)
        wss = record.get("working_set_size") if record else None
        _LOGGER.info(
            "census: %s working_set_size=%r (legitimately idle) — %s",
            engine_name,
            wss,
            reason,
        )

    catalogued = set(_EXPECTED_WORKING) | set(_LEGITIMATELY_IDLE)
    uncatalogued = sorted(set(records) - catalogued)
    if uncatalogued:
        _LOGGER.warning(
            "census: uncatalogued engines in response: %s — "
            "add them to _EXPECTED_WORKING or _LEGITIMATELY_IDLE",
            uncatalogued,
        )

    assert not failures, "\n".join(failures)
