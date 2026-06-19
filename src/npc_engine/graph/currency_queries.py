"""
currency_queries.py - Cypher query strings for currency transfer reads and writes.
Layer: graph
Purpose: Cypher query strings for currency transfer reads and writes.

Does NOT: execute queries or validate business rules.

Dependencies injected: None.
"""
from __future__ import annotations

CYPHER_GET_OUTBOUND_SESSION_TOTAL = """
MATCH (:Character {id: $source_id})-[t:TRANSFERRED_TO {session_scope: $session_scope, transfer_kind: $transfer_kind}]->(:Character)
RETURN coalesce(sum(toInteger(t.amount)), 0) AS total
"""

CYPHER_GET_CHARACTER_BALANCE = """
MATCH (c:Character {id: $character_id})
RETURN coalesce(c.currency_balance, 0) AS balance
"""

CYPHER_REPLAY_BY_IDEMPOTENCY = """
MATCH (src:Character {id: $source_id})-[t:TRANSFERRED_TO {
    idempotency_key: $idempotency_key,
    session_scope: $session_scope,
    transfer_kind: $transfer_kind
}]->(dst:Character {id: $destination_id})
RETURN t.request_id AS request_id,
       toInteger(t.amount) AS amount,
       coalesce(src.currency_balance, 0) AS source_balance,
       coalesce(dst.currency_balance, 0) AS destination_balance
LIMIT 1
"""

CYPHER_APPLY_TRANSFER = """
MATCH (src:Character {id: $source_id})
MATCH (dst:Character {id: $destination_id})
WHERE src.id <> dst.id
  AND coalesce(src.currency_balance, 0) >= $amount
SET src.currency_balance = coalesce(src.currency_balance, 0) - $amount,
    dst.currency_balance = coalesce(dst.currency_balance, 0) + $amount,
    src.last_graph_updated_at = datetime(),
    dst.last_graph_updated_at = datetime()
CREATE (src)-[:TRANSFERRED_TO {
    request_id: $request_id,
    idempotency_key: $idempotency_key,
    session_scope: $session_scope,
    transfer_kind: $transfer_kind,
    amount: $amount,
    reason: $reason,
    transferred_at: datetime()
}]->(dst)
RETURN coalesce(src.currency_balance, 0) AS source_balance,
       coalesce(dst.currency_balance, 0) AS destination_balance
"""

CYPHER_APPLY_SYSTEM_REWARD_TRANSFER = """
MERGE (src:Character {id: $source_id})
ON CREATE SET src.name = 'System Treasury',
              src.archetype = 'system',
              src.faction = 'system',
              src.biography = 'Synthetic reward source',
              src.is_player = false,
              src.is_active = true,
              src.currency_balance = coalesce(src.currency_balance, 0),
              src.created_at = datetime(),
              src.updated_at = datetime(),
              src.last_graph_updated_at = datetime()
WITH src
MATCH (dst:Character {id: $destination_id})
SET dst.currency_balance = coalesce(dst.currency_balance, 0) + $amount,
    src.last_graph_updated_at = datetime(),
    dst.last_graph_updated_at = datetime()
CREATE (src)-[:TRANSFERRED_TO {
    request_id: $request_id,
    idempotency_key: $idempotency_key,
    session_scope: $session_scope,
    transfer_kind: $transfer_kind,
    amount: $amount,
    reason: $reason,
    transferred_at: datetime()
}]->(dst)
RETURN coalesce(src.currency_balance, 0) AS source_balance,
       coalesce(dst.currency_balance, 0) AS destination_balance
"""
