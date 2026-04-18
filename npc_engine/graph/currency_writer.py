"""
currency_writer.py - Atomic currency transfer writes with audit edge persistence.

Does NOT: enforce business policy bounds.

Dependencies injected: AsyncSession.
"""

from pydantic import BaseModel, ConfigDict
from neo4j import AsyncSession, AsyncTransaction

from graph.replay_helpers import load_idempotent_replay_record
from utils.errors import CurrencyInsufficientFundsError, CurrencyValidationError, NodeNotFoundError


CURRENCY_ERR_TRANSFER_FAILED = "CURRENCY_TRANSFER_FAILED"

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
              src.current_location_id = 'system',
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


class CurrencyTransferWriteResult(BaseModel):
    """Stable return payload for currency writes."""

    request_id: str
    amount: int
    source_balance: int
    destination_balance: int
    replayed: bool

    model_config = ConfigDict(frozen=True)


async def get_outbound_session_total(
    session: AsyncSession,
    *,
    source_id: str,
    session_scope: str,
    transfer_kind: str,
) -> int:
    """Return outbound transfer total for source within one gameplay session scope."""

    result = await session.run(
        CYPHER_GET_OUTBOUND_SESSION_TOTAL,
        source_id=source_id,
        session_scope=session_scope,
        transfer_kind=transfer_kind,
    )
    record = await result.single()
    if record is None:
        return 0
    return int(record["total"])


async def get_character_balance(session: AsyncSession, *, character_id: str) -> int | None:
    """Return one character's current currency balance or None if node is missing."""

    result = await session.run(CYPHER_GET_CHARACTER_BALANCE, character_id=character_id)
    record = await result.single()
    if record is None:
        return None
    return int(record["balance"])


async def transfer_currency_atomic(
    session: AsyncSession,
    *,
    source_id: str,
    destination_id: str,
    amount: int,
    reason: str,
    request_id: str,
    idempotency_key: str,
    session_scope: str,
    transfer_kind: str,
) -> CurrencyTransferWriteResult:
    """Execute atomic debit/credit and audit edge write in one transaction."""

    tx = await session.begin_transaction()
    async with tx:
        replay = await _try_replay(
            tx=tx,
            source_id=source_id,
            destination_id=destination_id,
            idempotency_key=idempotency_key,
            session_scope=session_scope,
            transfer_kind=transfer_kind,
        )
        if replay is not None:
            await tx.commit()
            return replay

        result = await tx.run(
            (
                CYPHER_APPLY_SYSTEM_REWARD_TRANSFER
                if source_id == "system" and transfer_kind == "quest_reward"
                else CYPHER_APPLY_TRANSFER
            ),
            source_id=source_id,
            destination_id=destination_id,
            amount=amount,
            reason=reason,
            request_id=request_id,
            idempotency_key=idempotency_key,
            session_scope=session_scope,
            transfer_kind=transfer_kind,
        )
        record = await result.single()
        if record is None:
            await _raise_transfer_failure(
                tx=tx,
                source_id=source_id,
                destination_id=destination_id,
                amount=amount,
            )
        assert record is not None

        await tx.commit()
        return CurrencyTransferWriteResult(
            request_id=request_id,
            amount=amount,
            source_balance=int(record["source_balance"]),
            destination_balance=int(record["destination_balance"]),
            replayed=False,
        )


async def _try_replay(
    *,
    tx: AsyncTransaction,
    source_id: str,
    destination_id: str,
    idempotency_key: str,
    session_scope: str,
    transfer_kind: str,
) -> CurrencyTransferWriteResult | None:
    replay_record = await load_idempotent_replay_record(
        tx=tx,
        replay_cypher=CYPHER_REPLAY_BY_IDEMPOTENCY,
        params={
            "source_id": source_id,
            "destination_id": destination_id,
            "idempotency_key": idempotency_key,
            "session_scope": session_scope,
            "transfer_kind": transfer_kind,
        },
        idempotency_key=idempotency_key,
    )
    if replay_record is None:
        return None

    return CurrencyTransferWriteResult(
        request_id=str(replay_record["request_id"]),
        amount=int(replay_record["amount"]),
        source_balance=int(replay_record["source_balance"]),
        destination_balance=int(replay_record["destination_balance"]),
        replayed=True,
    )


async def _raise_transfer_failure(*, tx: AsyncTransaction, source_id: str, destination_id: str, amount: int) -> None:
    source_balance = await _read_balance(tx=tx, character_id=source_id)
    destination_balance = await _read_balance(tx=tx, character_id=destination_id)

    if source_balance is None:
        raise NodeNotFoundError(node_type="character", node_id=source_id)
    if destination_balance is None:
        raise NodeNotFoundError(node_type="character", node_id=destination_id)
    if source_balance < amount:
        raise CurrencyInsufficientFundsError(
            source_id=source_id,
            amount=amount,
            available_balance=source_balance,
        )

    raise CurrencyValidationError(
        code=CURRENCY_ERR_TRANSFER_FAILED,
        detail="Currency transfer did not match write guard conditions.",
    )


async def _read_balance(*, tx: AsyncTransaction, character_id: str) -> int | None:
    result = await tx.run(CYPHER_GET_CHARACTER_BALANCE, character_id=character_id)
    record = await result.single()
    if record is None:
        return None
    return int(record["balance"])
