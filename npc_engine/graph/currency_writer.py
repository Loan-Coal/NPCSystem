"""
currency_writer.py - Atomic currency transfer writes with audit edge persistence.

Does NOT: enforce business policy bounds.

Dependencies injected: AsyncSession.
"""

from neo4j import AsyncSession, AsyncTransaction
from pydantic import BaseModel, ConfigDict

from graph.currency_queries import (
    CYPHER_APPLY_SYSTEM_REWARD_TRANSFER,
    CYPHER_APPLY_TRANSFER,
    CYPHER_GET_CHARACTER_BALANCE,
    CYPHER_GET_OUTBOUND_SESSION_TOTAL,
    CYPHER_REPLAY_BY_IDEMPOTENCY,
)
from graph.replay_helpers import load_idempotent_replay_record
from utils.errors import CurrencyInsufficientFundsError, CurrencyValidationError, NodeNotFoundError


CURRENCY_ERR_TRANSFER_FAILED = "CURRENCY_TRANSFER_FAILED"


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
    """Return outbound transfer total for source within one gameplay session scope.

    Args:
        session: Active Neo4j async session for the read query.
        source_id: ID of the character whose outbound total is aggregated.
        session_scope: Opaque session identifier scoping the transfer window.
        transfer_kind: Transfer classification label to filter by.

    Returns:
        Integer sum of amounts already transferred this session, or 0 if none.
    """
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
    """Return one character's current currency balance or None if node is missing.

    Args:
        session: Active Neo4j async session for the read query.
        character_id: ID of the character node to query.

    Returns:
        Integer currency balance, or None if the character node does not exist.
    """
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
    """Execute atomic debit/credit and audit edge write in one transaction.

    Args:
        session: Active Neo4j async session used to begin the transaction.
        source_id: ID of the debited character; "system" triggers reward path.
        destination_id: ID of the credited character.
        amount: Positive integer amount to transfer.
        reason: Human-readable description persisted on the audit edge.
        request_id: Stable request identifier stored on the audit edge.
        idempotency_key: Client-supplied key for replay detection.
        session_scope: Opaque session identifier for outbound limit tracking.
        transfer_kind: Transfer classification label persisted on the audit edge.

    Returns:
        CurrencyTransferWriteResult with confirmed balances and replay flag.

    Raises:
        NodeNotFoundError: If source or destination character nodes are missing.
        CurrencyInsufficientFundsError: If source balance cannot cover the amount.
        CurrencyValidationError: If the transfer fails for other write-guard reasons.
    """
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
