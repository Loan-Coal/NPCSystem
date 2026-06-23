"""
Module: item_queries
Layer: graph
Purpose: Cypher query strings for item ownership (OWNS edge) and item transfer reads/writes.
Does NOT: execute queries or validate business rules.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.economy.item_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession, AsyncTransaction

# ---------------------------------------------------------------------------
# OWNS-based queries (Feature 3.6 — item nodes and ownership)
# ---------------------------------------------------------------------------

CYPHER_CREATE_ITEM_NODE = """
MERGE (i:Item {id: $item_id})
SET i.name = $name,
    i.description = $description,
    i.value = $value,
    i.rarity = $rarity,
    i.type = $type,
    i.is_unique = $is_unique,
    i.properties = $properties
WITH i
MATCH (c:Character {id: $character_id})
MERGE (c)-[:OWNS {acquired_at: $acquired_at}]->(i)
RETURN i.id AS item_id
"""

CYPHER_GET_ITEMS_FOR_CHARACTER = """
MATCH (c:Character {id: $character_id})-[:OWNS]->(i:Item)
RETURN i.id AS id,
       i.name AS name,
       i.description AS description,
       toInteger(i.value) AS value,
       i.rarity AS rarity,
       i.type AS type,
       i.is_unique AS is_unique,
       i.properties AS properties
ORDER BY toInteger(i.value) DESC
LIMIT $k
"""

CYPHER_GET_ITEM_BY_ID = """
MATCH (i:Item {id: $item_id})
RETURN i.id AS id,
       i.name AS name,
       i.description AS description,
       toInteger(i.value) AS value,
       i.rarity AS rarity,
       i.type AS type,
       i.is_unique AS is_unique,
       i.properties AS properties
"""

CYPHER_DETACH_ITEM_OWNER = """
MATCH (c:Character {id: $character_id})-[r:OWNS]->(i:Item {id: $item_id})
DELETE r
"""

CYPHER_ATTACH_ITEM_OWNER = """
MATCH (c:Character {id: $character_id}), (i:Item {id: $item_id})
MERGE (c)-[:OWNS {acquired_at: $acquired_at}]->(i)
"""

CYPHER_CHECK_ITEM_POSSESSION = """
MATCH (c:Character {id: $player_id})-[:OWNS]->(i:Item {id: $item_id})
RETURN count(i) >= $min_quantity AS has_sufficient
"""


async def check_item_possession_in_tx(
    tx: AsyncTransaction,
    *,
    player_id: str,
    item_id: str,
    min_quantity: int,
) -> bool:
    """Return True when the player owns at least min_quantity of item_id within a transaction.

    Args:
        tx: Active Neo4j transaction (caller owns commit/rollback).
        player_id: ID of the player character.
        item_id: ID of the Item node to check.
        min_quantity: Minimum required owned count.

    Returns:
        True if player owns at least min_quantity of item_id; False otherwise.
    """
    result = await tx.run(
        CYPHER_CHECK_ITEM_POSSESSION,
        player_id=player_id,
        item_id=item_id,
        min_quantity=min_quantity,
    )
    record = await result.single()
    if record is None:
        return False
    return bool(record["has_sufficient"])


async def get_items_for_character(
    session: AsyncSession,
    *,
    character_id: str,
    k: int = 10,
) -> list[dict[str, Any]]:
    """Fetch top-k items owned by a character via OWNS edges, ordered by value descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of items to return (default 10).

    Returns:
        List of item property dicts ordered by value descending.
    """
    result = await session.run(
        CYPHER_GET_ITEMS_FOR_CHARACTER,
        character_id=character_id,
        k=k,
    )
    return cast(
        list[dict[str, Any]],
        [dict(record) async for record in result],
    )


async def get_item_by_id(
    session: AsyncSession,
    *,
    item_id: str,
) -> dict[str, Any] | None:
    """Fetch a single item by its ID.

    Args:
        session: Active Neo4j async session.
        item_id: ID of the Item node.

    Returns:
        Item property dict, or None if not found.
    """
    result = await session.run(CYPHER_GET_ITEM_BY_ID, item_id=item_id)
    record = await result.single()
    if record is None:
        return None
    return cast(dict[str, Any], dict(record))


# ---------------------------------------------------------------------------
# Economy/trading queries (pre-existing — Phase P3 currency/item transfer)
# ---------------------------------------------------------------------------

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
MATCH (src)-[source_owns:OWNS]->(i:Item {id: $item_id})
WITH src, dst, i
OPTIONAL MATCH (:Character)-[all_owns:OWNS]->(i)
DELETE all_owns
CREATE (dst)-[:OWNS {acquired_at: datetime()}]->(i)
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
OPTIONAL MATCH (:Character)-[all_owns:OWNS]->(i)
DELETE all_owns
CREATE (dst)-[:OWNS {acquired_at: datetime()}]->(i)
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
