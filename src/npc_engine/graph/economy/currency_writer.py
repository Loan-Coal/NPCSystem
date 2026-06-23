"""
currency_writer.py - Atomic currency transfer writes with audit edge persistence.
Layer: graph
Purpose: Atomic currency transfer writes with audit edge persistence.

Does NOT: enforce business policy bounds.

Dependencies injected: AsyncSession.

NOTE: This file is 327 lines — over the 300-line limit by a small margin (DEC-058).
Splitting is artificial because execute_currency_transfer_in_tx shares private helpers
(_try_replay, _raise_transfer_failure) with transfer_currency_atomic.
"""
from __future__ import annotations

from typing import Any

from neo4j import AsyncSession, AsyncTransaction
from pydantic import BaseModel, ConfigDict

from npc_engine.config import Settings
from npc_engine.graph.economy.currency_queries import (
    CYPHER_APPLY_SYSTEM_REWARD_TRANSFER,
    CYPHER_APPLY_TRANSFER,
    CYPHER_GET_CHARACTER_BALANCE,
    CYPHER_GET_OUTBOUND_SESSION_TOTAL,
    CYPHER_REPLAY_BY_IDEMPOTENCY,
)
from npc_engine.graph.transaction_coordinator import run_in_tx
from npc_engine.graph.transfer_validators import build_currency_transfer_command
from npc_engine.graph.replay_helpers import load_idempotent_replay_record
from npc_engine.utils.errors import CurrencyInsufficientFundsError, CurrencyValidationError, NodeNotFoundError


CURRENCY_ERR_TRANSFER_FAILED = "CURRENCY_TRANSFER_FAILED"


class CurrencyTransferWriteResult(BaseModel):
    """Stable return payload for currency writes."""

    request_id: str
    amount: int
    source_balance: int
    destination_balance: int
    replayed: bool

    model_config = ConfigDict(frozen=True)


async def execute_currency_transfer_in_tx(
    tx: AsyncTransaction, *, settings: Settings, source_id: str, destination_id: str,
    amount: int, reason: str, request_id: str, idempotency_key: str, session_scope: str, transfer_kind: str,
) -> CurrencyTransferWriteResult:
    """Execute a validated currency transfer in an open transaction (idempotent via replay).

    Raises:
        NodeNotFoundError, CurrencyInsufficientFundsError, CurrencyValidationError.
    """
    replay = await _try_replay(tx=tx, source_id=source_id, destination_id=destination_id,
                               idempotency_key=idempotency_key, session_scope=session_scope, transfer_kind=transfer_kind)
    if replay is not None:
        return replay
    current_total = await _get_session_total_in_tx(tx, source_id=source_id, session_scope=session_scope, transfer_kind=transfer_kind)
    transfer_command = build_currency_transfer_command(
        settings=settings, source_id=source_id, destination_id=destination_id,
        amount=amount, reason=reason, session_scope=session_scope,
        transfer_kind=transfer_kind, current_session_total=current_total,
    )
    record = await _apply_transfer_in_tx(
        tx, source_id=transfer_command.source_id, destination_id=transfer_command.destination_id,
        amount=transfer_command.amount, reason=transfer_command.reason, request_id=request_id,
        idempotency_key=idempotency_key, session_scope=transfer_command.session_scope,
        transfer_kind=transfer_command.transfer_kind,
    )
    return CurrencyTransferWriteResult(
        request_id=request_id, amount=amount,
        source_balance=int(record["source_balance"]), destination_balance=int(record["destination_balance"]),
        replayed=False,
    )


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
    session: AsyncSession, *, source_id: str, destination_id: str,
    amount: int, reason: str, request_id: str, idempotency_key: str, session_scope: str, transfer_kind: str,
) -> CurrencyTransferWriteResult:
    """Execute atomic debit/credit and audit edge write in one transaction (idempotent).

    Raises:
        NodeNotFoundError, CurrencyInsufficientFundsError, CurrencyValidationError.
    """
    async def _work(tx: AsyncTransaction) -> CurrencyTransferWriteResult:
        replay = await _try_replay(tx=tx, source_id=source_id, destination_id=destination_id,
                                   idempotency_key=idempotency_key, session_scope=session_scope, transfer_kind=transfer_kind)
        if replay is not None:
            return replay
        record = await _apply_transfer_in_tx(
            tx, source_id=source_id, destination_id=destination_id, amount=amount, reason=reason,
            request_id=request_id, idempotency_key=idempotency_key, session_scope=session_scope,
            transfer_kind=transfer_kind,
        )
        return CurrencyTransferWriteResult(
            request_id=request_id, amount=amount,
            source_balance=int(record["source_balance"]), destination_balance=int(record["destination_balance"]),
            replayed=False,
        )

    return await run_in_tx(session, _work)


async def _get_session_total_in_tx(
    tx: AsyncTransaction, *, source_id: str, session_scope: str, transfer_kind: str
) -> int:
    """Return the outbound session total for source within the open transaction."""
    result = await tx.run(CYPHER_GET_OUTBOUND_SESSION_TOTAL, source_id=source_id, session_scope=session_scope, transfer_kind=transfer_kind)
    record = await result.single()
    return int(record["total"]) if record is not None else 0


async def _apply_transfer_in_tx(
    tx: AsyncTransaction, *, source_id: str, destination_id: str, amount: int, reason: str,
    request_id: str, idempotency_key: str, session_scope: str, transfer_kind: str,
) -> dict[str, Any]:
    """Select and run the correct transfer Cypher; raise on null result.

    Raises: NodeNotFoundError, CurrencyInsufficientFundsError, CurrencyValidationError.
    """
    cypher = CYPHER_APPLY_SYSTEM_REWARD_TRANSFER if source_id == "system" and transfer_kind == "quest_reward" else CYPHER_APPLY_TRANSFER
    result = await tx.run(cypher, source_id=source_id, destination_id=destination_id, amount=amount, reason=reason,
                          request_id=request_id, idempotency_key=idempotency_key, session_scope=session_scope, transfer_kind=transfer_kind)
    record = await result.single()
    if record is None:
        await _raise_transfer_failure(tx=tx, source_id=source_id, destination_id=destination_id, amount=amount)
    assert record is not None
    return dict(record)


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
