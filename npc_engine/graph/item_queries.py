"""
item_queries.py - Cypher query strings for item transfer reads and writes.

Does NOT: execute queries or validate business rules.

Dependencies injected: None.
"""

CYPHER_REPLAY_ITEM_TRANSFER = """
MATCH (src:Character {id: $source_id})-[t:TRANSFERRED_ITEM_TO {
    idempotency_key: $idempotency_key,
    transfer_kind: $transfer_kind,
    item_id: $item_id
}]->(dst:Character {id: $destination_id})
RETURN t.request_id AS request_id,
       t.item_id AS item_id,
       toInteger(t.quantity) AS quantity
LIMIT 1
"""

CYPHER_APPLY_ITEM_TRANSFER = """
MATCH (src:Character {id: $source_id})
MATCH (dst:Character {id: $destination_id})
WHERE src.id <> dst.id
MATCH (i:Item {id: $item_id})-[source_owned:OWNED_BY]->(src)
WITH src, dst, i
OPTIONAL MATCH (i)-[owned:OWNED_BY]->(:Character)
DELETE owned
CREATE (i)-[:OWNED_BY {updated_at: datetime()}]->(dst)
CREATE (src)-[:TRANSFERRED_ITEM_TO {
    request_id: $request_id,
    idempotency_key: $idempotency_key,
    transfer_kind: $transfer_kind,
    item_id: $item_id,
    quantity: $quantity,
    reason: $reason,
    transferred_at: datetime()
}]->(dst)
RETURN i.id AS item_id,
       toInteger($quantity) AS quantity
"""

CYPHER_GRANT_SYSTEM_ITEM = """
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
MERGE (i:Item {id: $item_instance_id})
ON CREATE SET i.created_at = datetime(),
              i.last_graph_updated_at = datetime(),
              i.name = $item_id
WITH src, dst, i
OPTIONAL MATCH (i)-[owned:OWNED_BY]->(:Character)
DELETE owned
CREATE (i)-[:OWNED_BY {updated_at: datetime()}]->(dst)
CREATE (src)-[:TRANSFERRED_ITEM_TO {
    request_id: $request_id,
    idempotency_key: $idempotency_key,
    transfer_kind: $transfer_kind,
    item_id: $item_id,
    quantity: $quantity,
    reason: $reason,
    transferred_at: datetime()
}]->(dst)
RETURN $item_id AS item_id,
       toInteger($quantity) AS quantity
"""
