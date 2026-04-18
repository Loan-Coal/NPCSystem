"""
test_quest_writer_queries_v14.py - Unit tests for quest writer Cypher query structure.

Does NOT: execute live Neo4j transactions.

Dependencies injected: none.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

pytest.importorskip("neo4j")

from graph.quest_writer import CYPHER_MERGE_QUEST_STATE
from graph.quest_writer import upsert_quest_state


@dataclass
class _ResultStub:
    async def consume(self):
        return None


class _RunnerStub:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def run(self, query: str, **params):
        self.calls.append((query, params))
        return _ResultStub()


def test_merge_query_places_on_create_set_before_generic_set_clause() -> None:
    normalized_query = " ".join(CYPHER_MERGE_QUEST_STATE.split())

    merge_pos = normalized_query.find("MERGE (q:QuestState {id: $id})")
    on_create_pos = normalized_query.find("ON CREATE SET q.created_at = datetime()")
    set_pos = normalized_query.find("SET q.quest_id = $quest_id")

    assert merge_pos != -1
    assert on_create_pos != -1
    assert set_pos != -1
    assert merge_pos < on_create_pos < set_pos


@pytest.mark.asyncio
async def test_upsert_quest_state_returns_detached_payload_copies() -> None:
    """Returned quest payload should not alias nested mutable input structures."""

    runner = _RunnerStub()
    state_payload = {
        "quest_id": "q1",
        "player_id": "p1",
        "reward_source_id": "system",
        "title": "Quest",
        "status": "offered",
        "objectives": [{"objective_id": "o1", "target_count": 1}],
        "objective_progress": {"o1": 0},
        "item_rewards": [{"item_id": "i1", "quantity": 1}],
        "currency_reward": {"amount": 10},
        "rewards_applied": False,
    }

    result = await upsert_quest_state(
        session=runner,
        quest_id="q1",
        player_id="p1",
        state_payload=state_payload,
    )

    result["objectives"][0]["target_count"] = 99
    result["item_rewards"][0]["quantity"] = 99
    result["objective_progress"]["o1"] = 99

    assert state_payload["objectives"][0]["target_count"] == 1
    assert state_payload["item_rewards"][0]["quantity"] == 1
    assert state_payload["objective_progress"]["o1"] == 0
