"""
Module: quest_node_queries
Layer: graph
Purpose: Cypher query strings for Quest node creation and retrieval.
Does NOT: execute business logic or validate payloads.
Dependencies: None (Cypher strings only).
Dependencies injected: None.
Used by: npc_engine.graph.quest_node_service
"""

from __future__ import annotations

CYPHER_CREATE_QUEST = """
MERGE (q:Quest {id: $quest_id})
SET q.description       = $description,
    q.quest_giver_id    = $quest_giver_id,
    q.target_id         = $target_id,
    q.reward_id         = $reward_id,
    q.success_condition = $success_condition,
    q.failure_condition = $failure_condition,
    q.status            = $status,
    q.severity          = $severity,
    q.created_at        = $created_at,
    q.completed_at      = $completed_at
WITH q
MATCH (c:Character {id: $quest_giver_id})
MERGE (c)-[:HAS_QUEST]->(q)
RETURN q.id AS quest_id
"""

CYPHER_GET_QUEST = """
MATCH (q:Quest {id: $quest_id})
RETURN q.id              AS id,
       q.description     AS description,
       q.quest_giver_id  AS quest_giver_id,
       q.target_id       AS target_id,
       q.reward_id       AS reward_id,
       q.success_condition AS success_condition,
       q.failure_condition AS failure_condition,
       q.status          AS status,
       toInteger(q.severity) AS severity,
       q.created_at      AS created_at,
       q.completed_at    AS completed_at
"""
