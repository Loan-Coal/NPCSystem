"""
item_writer.py - Atomic item transfer writes with idempotent replay support.

Does NOT: enforce business policy bounds.

Dependencies injected: AsyncSession.
"""

from __future__ import annotations

from neo4j import AsyncSession, AsyncTransaction
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.graph.item_queries import CYPHER_APPLY_ITEM_TRANSFER, CYPHER_GRANT_SYSTEM_ITEM, CYPHER_REPLAY_ITEM_TRANSFER
from npc_engine.graph.replay_helpers import load_idempotent_replay_record
from npc_engine.utils.errors import ItemTransferValidationError, NodeNotFoundError


class ItemTransferWriteResult(BaseModel):
    """Stable return payload for item transfer writes."""

    request_id: str
    item_id: str
    quantity: int = Field(ge=1)
    replayed: bool

    model_config = ConfigDict(frozen=True)


async def execute_item_transfer_in_tx(
    tx: AsyncTransaction,
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
    """Execute item ownership transfer within an already-open transaction.

    The caller owns the transaction lifecycle (commit/rollback). This function
    does not open or commit a transaction.

    Args:
        tx: Active Neo4j transaction provided by the caller.
        source_id: ID of the character giving the item; ``"system"`` triggers grant path.
        destination_id: ID of the character receiving the item.
        item_id: Identifier of the item being transferred.
        quantity: Positive integer count of items.
        reason: Human-readable description persisted on the audit edge.
        request_id: Stable request identifier stored on the audit edge.
        idempotency_key: Client-supplied key for replay detection.
        transfer_kind: Transfer classification label persisted on the audit edge.

    Returns:
        ItemTransferWriteResult with confirmed item/quantity and replay flag.

    Raises:
        NodeNotFoundError: If source or destination character nodes are missing.
        ItemTransferValidationError: If the item transfer fails write-guard conditions.
    """
    replay = await _try_replay(
        tx=tx,
        source_id=source_id,
        destination_id=destination_id,
        idempotency_key=idempotency_key,
        transfer_kind=transfer_kind,
        item_id=item_id,
    )
    if replay is not None:
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

    return ItemTransferWriteResult(
        request_id=request_id,
        item_id=str(record["item_id"]),
        quantity=int(record["quantity"]),
        replayed=False,
    )


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
    """Execute atomic item ownership transfer with idempotent replay handling.

    Args:
        session: Active Neo4j async session used to begin the transaction.
        source_id: ID of the character giving the item; "system" triggers grant path.
        destination_id: ID of the character receiving the item.
        item_id: Identifier of the item being transferred.
        quantity: Positive integer count of items (persisted on the audit edge).
        reason: Human-readable description persisted on the audit edge.
        request_id: Stable request identifier stored on the audit edge.
        idempotency_key: Client-supplied key for replay detection.
        transfer_kind: Transfer classification label persisted on the audit edge.

    Returns:
        ItemTransferWriteResult with confirmed item/quantity and replay flag.

    Raises:
        NodeNotFoundError: If source or destination character nodes are missing.
        ItemTransferValidationError: If the item transfer fails write-guard conditions.
    """
    tx = await session.begin_transaction()
    async with tx:
        result = await execute_item_transfer_in_tx(
            tx,
            source_id=source_id,
            destination_id=destination_id,
            item_id=item_id,
            quantity=quantity,
            reason=reason,
            request_id=request_id,
            idempotency_key=idempotency_key,
            transfer_kind=transfer_kind,
        )
        await tx.commit()
        return result


async def _raise_item_transfer_failure(*, tx: AsyncTransaction, source_id: str, destination_id: str) -> None:
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


async def _character_exists(*, tx: AsyncTransaction, character_id: str) -> bool:
    result = await tx.run("MATCH (c:Character {id: $character_id}) RETURN c.id AS id", character_id=character_id)
    return await result.single() is not None


async def _try_replay(
    *,
    tx: AsyncTransaction,
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
