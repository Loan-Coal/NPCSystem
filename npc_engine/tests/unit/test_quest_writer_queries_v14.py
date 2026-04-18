"""
test_quest_writer_queries_v14.py - Unit tests for quest writer Cypher query structure.

Does NOT: execute live Neo4j transactions.

Dependencies injected: none.
"""

from __future__ import annotations

from graph.quest_writer import CYPHER_MERGE_QUEST_STATE


def test_merge_query_places_on_create_set_before_generic_set_clause() -> None:
    normalized_query = " ".join(CYPHER_MERGE_QUEST_STATE.split())

    merge_pos = normalized_query.find("MERGE (q:QuestState {id: $id})")
    on_create_pos = normalized_query.find("ON CREATE SET q.created_at = datetime()")
    set_pos = normalized_query.find("SET q.quest_id = $quest_id")

    assert merge_pos != -1
    assert on_create_pos != -1
    assert set_pos != -1
    assert merge_pos < on_create_pos < set_pos
