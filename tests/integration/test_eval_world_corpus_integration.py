"""
Module: test_eval_world_corpus_integration
Layer: test (integration)
Purpose: Pin the eval-world corpus anchors — a bounded, PascalCase-labelled node census
    and a RAG scope that does not grow while the engine ticks (M1.3, ISSUE-221/ISSUE-273).
Dependencies: neo4j async driver, npc_engine.graph.graph_rag_queries.
Used by: make test-integration.

Does NOT: seed the world. These tests measure whatever graph the configured Neo4j holds.

The quiescence test deliberately refuses to pass on a stopped app: it waits for the
world tick counter to advance and fails if it does not. A scope that is stable because
nothing is writing is not evidence of quiescence (plan step 3, "honest note on anchor 2").
"""

from __future__ import annotations

import asyncio
import os
import time

import httpx
import pytest
from neo4j import AsyncGraphDatabase, AsyncSession

from npc_engine.graph.graph_rag_queries import get_rag_scope_ids_for_npc

# Corpus ceiling. The seeded three-world fixture is ~250 nodes; anything approaching four
# figures means derived state (Quest, TickLease) has leaked back into the frozen corpus.
MAX_CORPUS_NODES = 1_000

# The NPC whose RAG scope is the quiescence probe. Seeded by demo_game/seeds/seed.py:686.
QUIESCENCE_NPC_ID = "captain_sorn"

# The singleton world clock the tick scheduler advances (`WorldState {id: "world"}`).
WORLD_STATE_ID = "world"

# Two ticks, so the observation spans a full gossip and event cycle rather than landing
# inside one. GOSSIP_TICK_INTERVAL=10 / EVENT_TICK_INTERVAL=20 in .env.
MIN_TICKS_OBSERVED = 2
DEFAULT_EVENT_TICK_INTERVAL_S = 20
TICK_POLL_INTERVAL_S = 2.0
TICK_WAIT_MARGIN_S = 30.0

# Set to "1" by `make check-corpus-frozen`. When set, an app that is still ticking is a
# gate FAILURE rather than a skip — a gate that skips itself is not a gate (ISSUE-236's
# lesson, applied here: assert the check actually executed).
REQUIRE_FROZEN_ENV = "REQUIRE_FROZEN_CORPUS"

# Set to "1" by `make check-corpus-quiescent`. The quiescence anchor and the freeze gate
# have opposite preconditions — one needs ticks flowing, the other needs them stopped —
# so each skips when the engine is in the other mode and each has an env switch that
# turns that skip into a failure for its own gate. Neither can pass vacuously.
REQUIRE_TICKING_ENV = "REQUIRE_TICKING_CORPUS"

DEFAULT_BASE_URL = "http://localhost:8000"
FROZEN_OBSERVE_TICKS = 2

_CYPHER_LABEL_CENSUS = "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count"
_CYPHER_WORLD_TICK = "MATCH (w:WorldState {id: $world_id}) RETURN w.tick_id AS tick_id"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


def _tick_wait_timeout_s() -> float:
    """Return how long to wait for MIN_TICKS_OBSERVED ticks, from the configured interval."""
    interval = int(os.getenv("EVENT_TICK_INTERVAL", str(DEFAULT_EVENT_TICK_INTERVAL_S)))
    return MIN_TICKS_OBSERVED * interval + TICK_WAIT_MARGIN_S


async def _label_census(session: AsyncSession) -> dict[str, int]:
    result = await session.run(_CYPHER_LABEL_CENSUS)
    rows = await result.data()
    return {str(row["label"]): int(row["count"]) for row in rows if row.get("label")}


async def _read_world_tick(session: AsyncSession) -> int | None:
    result = await session.run(_CYPHER_WORLD_TICK, world_id=WORLD_STATE_ID)
    row = await result.single()
    if row is None or row["tick_id"] is None:
        return None
    return int(row["tick_id"])


async def _await_ticks(session: AsyncSession, *, start_tick: int) -> int:
    """Block until the world tick counter has advanced by MIN_TICKS_OBSERVED.

    Args:
        session: Active Neo4j async session.
        start_tick: The tick counter value read before the observation window opened.
    Returns:
        The tick counter value once it has advanced far enough.
    Raises:
        AssertionError: If the counter did not advance in time, which means the app is
            not ticking and any stability seen here would be vacuous.
    """
    deadline = time.monotonic() + _tick_wait_timeout_s()
    latest = start_tick
    while time.monotonic() < deadline:
        await asyncio.sleep(TICK_POLL_INTERVAL_S)
        current = await _read_world_tick(session)
        if current is not None:
            latest = current
            if current - start_tick >= MIN_TICKS_OBSERVED:
                return current
    raise AssertionError(
        f"world tick advanced {latest - start_tick} of {MIN_TICKS_OBSERVED} required "
        f"within {_tick_wait_timeout_s():.0f}s (start={start_tick}, last={latest}). "
        "The app container must be running for the quiescence anchor to mean anything."
    )


async def test_corpus_node_census_is_under_ceiling() -> None:
    uri, user, password = _skip_if_no_neo4j()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            census = await _label_census(session)
    finally:
        await driver.close()

    total = sum(census.values())
    biggest = sorted(census.items(), key=lambda kv: kv[1], reverse=True)[:5]
    assert total < MAX_CORPUS_NODES, (
        f"corpus holds {total} nodes, ceiling is {MAX_CORPUS_NODES}; largest labels: {biggest}"
    )


async def test_corpus_has_no_lowercase_node_labels() -> None:
    uri, user, password = _skip_if_no_neo4j()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            census = await _label_census(session)
    finally:
        await driver.close()

    lowercase = {label: count for label, count in census.items() if label[:1].islower()}
    assert not lowercase, (
        f"lowercase node labels present: {lowercase}. Every writer must resolve through "
        "resolve_node_label, which returns the PascalCase label graph/ queries."
    )


async def test_rag_scope_is_quiescent_while_ticks_flow() -> None:
    uri, user, password = _skip_if_no_neo4j()
    if not await _read_autopilot_enabled():
        message = (
            "tick autopilot is DISABLED, so no ticks will flow and scope stability here "
            "would prove nothing. Bring the stack up without docker-compose.freeze.yml "
            "to measure the quiescence anchor."
        )
        if os.getenv(REQUIRE_TICKING_ENV) == "1":
            pytest.fail(message)
        pytest.skip(message)
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            start_tick = await _read_world_tick(session)
            assert start_tick is not None, (
                f"WorldState {{id: '{WORLD_STATE_ID}'}} has no tick_id; cannot prove ticks flowed"
            )
            before = await get_rag_scope_ids_for_npc(session, npc_id=QUIESCENCE_NPC_ID)
            assert before, f"{QUIESCENCE_NPC_ID} has an empty RAG scope; the world is not seeded"
            end_tick = await _await_ticks(session, start_tick=start_tick)
            after = await get_rag_scope_ids_for_npc(session, npc_id=QUIESCENCE_NPC_ID)
    finally:
        await driver.close()

    assert after == before, (
        f"RAG scope for {QUIESCENCE_NPC_ID} grew from {len(before)} to {len(after)} ids "
        f"across ticks {start_tick}->{end_tick}; added={sorted(after - before)}, "
        f"removed={sorted(before - after)}"
    )


async def test_rag_scope_is_empty_for_unknown_npc() -> None:
    uri, user, password = _skip_if_no_neo4j()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            scope = await get_rag_scope_ids_for_npc(session, npc_id="npc_that_does_not_exist")
    finally:
        await driver.close()

    assert scope == set()


def _api_base_url() -> str:
    return os.getenv("BASE_URL", DEFAULT_BASE_URL)


async def _read_autopilot_enabled() -> bool:
    """Return whether the running app has its tick autopilot enabled.

    Returns:
        The `tick_autopilot_enabled` field of GET /v1/admin/system/config.
    Raises:
        pytest.skip.Exception: If the app is unreachable or rejects the request, since
            without it there is nothing to assert about the running engine.
    """
    key = os.getenv("API_KEY_SECRET", "")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{_api_base_url()}/v1/admin/system/config", headers=headers)
    except httpx.HTTPError as exc:
        pytest.skip(f"app unreachable at {_api_base_url()}: {exc}")
    if response.status_code != 200:
        pytest.skip(f"GET /v1/admin/system/config returned {response.status_code}; cannot read autopilot state")
    return bool(response.json()["data"]["tick_autopilot_enabled"])


async def test_corpus_does_not_grow_while_autopilot_is_frozen() -> None:
    uri, user, password = _skip_if_no_neo4j()
    required = os.getenv(REQUIRE_FROZEN_ENV) == "1"
    autopilot_on = await _read_autopilot_enabled()
    if autopilot_on:
        message = (
            "tick autopilot is ENABLED, so the corpus is still growing "
            "(~6 FactionStandingEvent + ~1 Event per tick). Bring the stack up with "
            "`make app-frozen` before measuring against a frozen corpus."
        )
        if required:
            pytest.fail(message)
        pytest.skip(message)

    interval = int(os.getenv("TICK_INTERVAL_SECONDS", "10"))
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            before = await _label_census(session)
            await asyncio.sleep(FROZEN_OBSERVE_TICKS * interval + TICK_POLL_INTERVAL_S)
            after = await _label_census(session)
    finally:
        await driver.close()

    grown = {
        label: (before.get(label, 0), count)
        for label, count in after.items()
        if count != before.get(label, 0)
    }
    assert not grown, (
        f"corpus changed while the autopilot was frozen, label -> (before, after): {grown}. "
        "Something other than the tick autopilot is writing to the graph."
    )
