"""
Module: test_revived_engines_do_work
Layer: test (integration)
Purpose: Confirm that after T5.1/T5.2 seed edits, routine moves characters and
    need_decay decays needs — both engines do visible work on the isolated eval
    stack (localhost:8001).

RED anchor (against tree before T5.1, commit da96cde6):
    routine returned moved=0 (no FOLLOWS_SCHEDULE edges) and need_decay returned
    needs_updated=0 (no HAS_NEED edges). This test therefore failed. That failure
    is the evidence the T5.x sprint was needed.

Does NOT: run without the eval stack; writes nothing to the graph; seed the world.
Dependencies: httpx (HTTP clock advance), neo4j async driver (unmet-need check).
Used by: T6.3 validation (eval stack only, not make test-integration).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
import pytest
from neo4j import AsyncGraphDatabase

_LOGGER = logging.getLogger(__name__)

# Eval stack endpoints — override via env if not using defaults.
_EVAL_BASE_URL: str = os.getenv("EVAL_BASE_URL", "http://localhost:8001")
_EVAL_NEO4J_URI: str = os.getenv("EVAL_NEO4J_URI", "bolt://localhost:7688")
_EVAL_NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
_EVAL_NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")

# A need is "unmet" when its level is strictly below this threshold.
# Mirrors NEED_UNMET_LEVEL_THRESHOLD in context_need_models.py.
_NEED_UNMET_THRESHOLD: int = 50

# Number of ticks to advance. Two ticks guarantees a time_of_day transition
# so routine sees a new slot and must re-place characters.
_ADVANCE_TICKS: int = 3

# Cypher: find any Need whose level is below the unmet threshold.
_CYPHER_UNMET_NEED = (
    "MATCH (c:Character)-[:HAS_NEED]->(n:Need) "
    "WHERE n.level < $threshold "
    "RETURN c.id AS character_id, n.kind AS kind, n.level AS level "
    "LIMIT 1"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_api_key() -> str:
    """Return the eval-stack API key from EVAL_API_KEY, defaulting to the dev secret.

    Uses EVAL_API_KEY (not API_KEY_SECRET) to avoid picking up the
    test-collection stub that conftest.py seeds via setdefault.
    Override EVAL_API_KEY when running against a non-default eval stack.

    Returns:
        Bearer token string for Authorization header.
    """
    return os.getenv("EVAL_API_KEY", "local_dev_secret_change_this_2026")


def _auth_headers() -> dict[str, str]:
    """Return the Authorization header dict for eval-stack API calls.

    Returns:
        Dict with Authorization Bearer token.
    """
    return {"Authorization": f"Bearer {_read_api_key()}"}


def _skip_if_no_eval_stack() -> None:
    """Skip the calling test if the eval stack is not reachable at _EVAL_BASE_URL."""
    try:
        r = httpx.get(f"{_EVAL_BASE_URL}/health", timeout=5.0)
        r.raise_for_status()
    except Exception as exc:
        pytest.skip(f"eval stack not reachable at {_EVAL_BASE_URL}: {exc}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routine_and_need_decay_do_work() -> None:
    """routine moves characters and need_decay decays needs after T5.1/T5.2 seeding.

    Advances the clock one tick at a time (_ADVANCE_TICKS total). On each tick,
    the time_of_day also advances so routine encounters a new scheduled slot and
    must re-place characters. After all ticks:

    - routine.moved sum > 0 (characters relocated at least once).
    - need_decay.needs_updated sum > 0 (at least one need level changed).
    - GET /v1/admin/system/engines shows tick_count > 0 for both engines.

    A zero with visible LLM timeout errors in the response is a Sprint-4
    ordering artifact (need_quest_trigger amplification before admission
    control lands), NOT evidence T5.2 failed. A zero with a clean log is
    the real regression signal.
    """
    _skip_if_no_eval_stack()

    total_moved = 0
    total_needs_updated = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(_ADVANCE_TICKS):
            payload: dict[str, Any] = {"delta_ticks": 1, "game_time_seconds": 1}
            if i > 0:
                # Advance time_of_day so routine sees a new slot on tick 2+.
                payload["advance_time_field"] = "time_of_day"

            resp = await client.post(
                f"{_EVAL_BASE_URL}/v1/clock/advance",
                json=payload,
                headers=_auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json()["data"]

            tick_moved = sum(entry.get("moved", 0) for entry in data.get("routine", []))
            tick_updated = sum(
                entry.get("needs_updated", 0) for entry in data.get("need_decay", [])
            )
            _LOGGER.info(
                "tick %d: routine.moved=%d need_decay.needs_updated=%d",
                i + 1,
                tick_moved,
                tick_updated,
            )
            total_moved += tick_moved
            total_needs_updated += tick_updated

    assert total_moved > 0, (
        f"routine.moved=0 across {_ADVANCE_TICKS} ticks — "
        "FOLLOWS_SCHEDULE edges missing? (T5.1 seed not applied)"
    )
    assert total_needs_updated > 0, (
        f"need_decay.needs_updated=0 across {_ADVANCE_TICKS} ticks — "
        "HAS_NEED edges missing? (T5.2 seed not applied)"
    )

    # Engine status confirms both engines registered runs.
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_EVAL_BASE_URL}/v1/admin/system/engines",
            headers=_auth_headers(),
        )
        resp.raise_for_status()
        records: dict[str, Any] = {
            rec["engine_name"]: rec for rec in resp.json()["data"]
        }

    assert "routine" in records, (
        "routine absent from /v1/admin/system/engines — engine never registered"
    )
    assert records["routine"]["tick_count"] > 0, (
        "routine.tick_count == 0; engine registered but never ran"
    )
    assert "need_decay" in records, (
        "need_decay absent from /v1/admin/system/engines — engine never registered"
    )
    assert records["need_decay"]["tick_count"] > 0, (
        "need_decay.tick_count == 0; engine registered but never ran"
    )


@pytest.mark.asyncio
async def test_npc_top_need_is_populated() -> None:
    """At least one NPC has an unmet need (level < 50) after seeding and decay.

    This is the user-visible half of ISSUE-210: dialogue context picks up
    `npc.top_need` only when a Character has a Need node below the unmet
    threshold. Verifies that seed + need_decay leave the graph in a state
    where that context slot fires.
    """
    _skip_if_no_eval_stack()
    if not _EVAL_NEO4J_URI or not _EVAL_NEO4J_USER or not _EVAL_NEO4J_PASSWORD:
        pytest.skip("EVAL_NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD required")

    driver = AsyncGraphDatabase.driver(
        _EVAL_NEO4J_URI,
        auth=(_EVAL_NEO4J_USER, _EVAL_NEO4J_PASSWORD),
    )
    try:
        async with driver.session() as session:
            result = await session.run(
                _CYPHER_UNMET_NEED,
                threshold=_NEED_UNMET_THRESHOLD,
            )
            row = await result.single()
    finally:
        await driver.close()

    assert row is not None, (
        f"No Character has a Need with level < {_NEED_UNMET_THRESHOLD}. "
        "Either HAS_NEED edges are missing (T5.2 not applied) or need_decay "
        "clamped all levels. "
        "Diagnostic: MATCH (c)-[:HAS_NEED]->(n:Need) RETURN c.id, n.level."
    )
    _LOGGER.info(
        "top_need populated: character=%s kind=%s level=%d",
        row["character_id"],
        row["kind"],
        row["level"],
    )
