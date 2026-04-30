"""
item_writer.py - Atomic item transfer writes with idempotent replay support.

Does NOT: enforce business policy bounds.

Dependencies injected: AsyncSession.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from neo4j import AsyncSession

from graph.replay_helpers import load_idempotent_replay_record
from utils.errors import ItemTransferValidationError, NodeNotFoundError


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


class ItemTransferWriteResult(BaseModel):
    """Stable return payload for item transfer writes."""

    request_id: str
    item_id: str
    quantity: int = Field(ge=1)
    replayed: bool

    model_config = ConfigDict(frozen=True)


async def transfer_item_atomic(
    session: AsyncSession,
    *,
    source_id: str,
    destination_id: str,
    item_id: str,
    quantity: int,
    reason: str,
    request_id: str,
    idempotency_key: str,
    transfer_kind: str,
) -> ItemTransferWriteResult:
    """Execute atomic item ownership transfer with idempotent replay handling."""

    tx = await session.begin_transaction()
    async with tx:
        replay = await _try_replay(
            tx=tx,
            source_id=source_id,
            destination_id=destination_id,
            idempotency_key=idempotency_key,
            transfer_kind=transfer_kind,
            item_id=item_id,
        )
        if replay is not None:
            await tx.commit()
            return replay

        result = await tx.run(
            CYPHER_GRANT_SYSTEM_ITEM if source_id == "system" and transfer_kind == "quest_reward" else CYPHER_APPLY_ITEM_TRANSFER,
            source_id=source_id,
            destination_id=destination_id,
            item_id=item_id,
            item_instance_id=f"{item_id}:{idempotency_key}" if idempotency_key != "" else f"{item_id}:{request_id}",
            quantity=quantity,
            reason=reason,
            request_id=request_id,
            idempotency_key=idempotency_key,
            transfer_kind=transfer_kind,
        )
        record = await result.single()
        if record is None:
            await _raise_item_transfer_failure(tx=tx, source_id=source_id, destination_id=destination_id)
        assert record is not None

        await tx.commit()
        return ItemTransferWriteResult(
            request_id=request_id,
            item_id=str(record["item_id"]),
            quantity=int(record["quantity"]),
            replayed=False,
        )


async def _raise_item_transfer_failure(*, tx, source_id: str, destination_id: str) -> None:
    source_exists = await _character_exists(tx=tx, character_id=source_id)
    destination_exists = await _character_exists(tx=tx, character_id=destination_id)
    if not source_exists:
        raise NodeNotFoundError(node_type="character", node_id=source_id)
    if not destination_exists:
        raise NodeNotFoundError(node_type="character", node_id=destination_id)
    raise ItemTransferValidationError(
        code="ITEM_TRANSFER_FAILED",
        detail="Item transfer did not match write guard conditions",
    )


async def _character_exists(*, tx, character_id: str) -> bool:
    result = await tx.run("MATCH (c:Character {id: $character_id}) RETURN c.id AS id", character_id=character_id)
    return await result.single() is not None


async def _try_replay(
    *,
    tx,
    source_id: str,
    destination_id: str,
    idempotency_key: str,
    transfer_kind: str,
    item_id: str,
) -> ItemTransferWriteResult | None:
    replay_record = await load_idempotent_replay_record(
        tx=tx,
        replay_cypher=CYPHER_REPLAY_ITEM_TRANSFER,
        params={
            "source_id": source_id,
            "destination_id": destination_id,
            "idempotency_key": idempotency_key,
            "transfer_kind": transfer_kind,
            "item_id": item_id,
        },
        idempotency_key=idempotency_key,
    )
    if replay_record is None:
        return None
    return ItemTransferWriteResult(
        request_id=str(replay_record["request_id"]),
        item_id=str(replay_record["item_id"]),
        quantity=int(replay_record["quantity"]),
        replayed=True,
    )
