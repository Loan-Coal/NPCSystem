"""
test_knowledge_writer.py - Unit tests for write_belief stable-id dedup (ISSUE-089).

Two identical fact writes for the same (npc_id, content) must produce the same
belief_id so the Cypher MERGE deduplicates instead of inserting a fresh node each call.

Does NOT: connect to Neo4j (the transaction is faked).
"""

from __future__ import annotations

from typing import cast

import pytest
from neo4j import AsyncSession

from npc_engine.graph.knowledge_writer import write_belief


class _FakeTx:
    def __init__(self) -> None:
        self.run_calls: list[dict] = []

    async def run(self, query: str, **params):
        self.run_calls.append(params)
        return None

    async def commit(self):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, tx: _FakeTx) -> None:
        self._tx = tx

    async def begin_transaction(self):
        return self._tx


async def _write(npc_id: str, content: str) -> tuple[str, dict]:
    tx = _FakeTx()
    session = _FakeSession(tx=tx)
    belief_id = await write_belief(
        session=cast(AsyncSession, session),
        npc_id=npc_id,
        content=content,
        confidence=80,
        source_character_id="player_1",
        learned_at_tick=5,
        game_time_str="Year 1 spring Day 1 morning",
    )
    return belief_id, tx.run_calls[0]


@pytest.mark.asyncio
async def test_identical_fact_writes_produce_same_belief_id():
    id_a, params_a = await _write("mira_innkeeper", "the bridge is out")
    id_b, params_b = await _write("mira_innkeeper", "the bridge is out")
    assert id_a == id_b
    assert params_a["belief_id"] == params_b["belief_id"] == id_a


@pytest.mark.asyncio
async def test_different_content_produces_different_belief_id():
    id_a, _ = await _write("mira_innkeeper", "the bridge is out")
    id_b, _ = await _write("mira_innkeeper", "the well is poisoned")
    assert id_a != id_b


@pytest.mark.asyncio
async def test_different_npc_produces_different_belief_id():
    id_a, _ = await _write("mira_innkeeper", "the bridge is out")
    id_b, _ = await _write("aldric_merchant", "the bridge is out")
    assert id_a != id_b
