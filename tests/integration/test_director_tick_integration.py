"""
test_director_tick_integration.py - Integration test for F1.5: DirectorTick emits a
beat against a live Neo4j session when the director's decide() fires.

Uses a controlled fake location reader (one pair + high idle count) so the co-location
path is deterministic. The RELATES_TO scalars come from a real graph edge seeded here.

Does NOT: test HTTP route wiring, LLM calls, or the full scheduler path.

Dependencies: Neo4j test environment via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.engines.director.director_tick import DirectorTick
from npc_engine.api.dependencies_engines import get_event_handler


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


class _FakeLocationReader:
    """Returns a fixed (npc, player) pair and a configurable idle count."""

    def __init__(self, pairs: list[tuple[str, str]], idle: int = 15) -> None:
        self._pairs = pairs
        self._idle = idle

    async def get_collocated_pairs(self, session: Any) -> list[tuple[str, str]]:
        return self._pairs

    async def get_player_idle_ticks(
        self,
        session: Any,
        *,
        npc_id: str,
        player_id: str,
        tick_id: int,
    ) -> int:
        return self._idle


async def _create_characters_and_edge(tx, npc_id: str, player_id: str) -> None:
    await tx.run(
        "MERGE (a:Character {id: $npc_id, is_player: false, is_active: true}) "
        "MERGE (b:Character {id: $player_id, is_player: true}) "
        "MERGE (a)-[r:RELATES_TO]->(b) SET r.trust = 5, r.fear = 0, r.affection = 5",
        npc_id=npc_id,
        player_id=player_id,
    )


async def _cleanup(tx, *ids: str) -> None:
    for node_id in ids:
        await tx.run("MATCH (n {id: $id}) DETACH DELETE n", id=node_id)


@pytest.mark.asyncio
async def test_director_tick_fires_beat_against_live_session() -> None:
    """DirectorTick with high idle triggers decide(), calls event_handler, returns beat."""
    uri, user, password = _skip_if_no_neo4j()

    npc_id = _uid("dir-npc")
    player_id = _uid("dir-plr")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_characters_and_edge(tx, npc_id, player_id)
                await tx.commit()

            # idle=15 > IDLE_INJECT_THRESHOLD_TICKS (10) → re_engage_idle decision
            adapter = DirectorTick(
                location_reader=_FakeLocationReader([(npc_id, player_id)], idle=15),
                event_handler=get_event_handler(),
            )
            result = await adapter.run_tick(session=session, tick_id=99)

        assert len(result["director_beats"]) == 1, (
            f"Expected one beat but got: {result['director_beats']}"
        )
        beat = result["director_beats"][0]
        assert beat["beat_kind"] == "re_engage_idle"
        assert beat["npc_id"] == npc_id
        assert beat["player_id"] == player_id
        assert "event" in beat
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, npc_id, player_id)
                await tx.commit()
        await driver.close()
