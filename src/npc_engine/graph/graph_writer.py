"""
graph_writer.py - Transaction coordinator for currency and item mutation workflows.
Layer: graph
Purpose: (auto-detected — review)

Does NOT: define mutation policy bounds or apply relation deltas.

Dependencies injected: AsyncSession, Settings.
"""

from time import perf_counter
from typing import Literal

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.graph.currency_writer import get_outbound_session_total, transfer_currency_atomic
from npc_engine.graph.item_writer import transfer_item_atomic
from npc_engine.graph.relation_delta_writer import apply_relation_delta as apply_relation_delta
from npc_engine.graph.transfer_validators import build_currency_transfer_command, build_item_transfer_command
from npc_engine.graph.write_metrics import CURRENCY_TRANSFERS_METRIC, record_graph_write_metrics
from npc_engine.utils.metrics import increment_metric

__all__ = [
    "apply_buy_sell_currency_transfer",
    "apply_currency_transfer",
    "apply_item_transfer",
    "apply_relation_delta",
]


async def apply_buy_sell_currency_transfer(
    *,
    session: AsyncSession,
    settings: Settings,
    player_id: str,
    counterparty_id: str,
    action_type: Literal["buy_item", "sell_item"],
    amount: int,
    reason: str,
    request_id: str,
    idempotency_key: str,
    session_scope: str,
) -> dict[str, int | str | bool]:
    """Apply buy/sell currency mutation through one validated transaction path.

    Args:
        session: Active Neo4j async session.
        settings: Application settings providing transfer bound configuration.
        player_id: ID of the player character initiating the action.
        counterparty_id: ID of the NPC or merchant counterparty.
        action_type: Direction of the transfer ("buy_item" debits player, "sell_item" credits player).
        amount: Positive integer amount to transfer.
        reason: Human-readable description persisted on the audit edge.
        request_id: Stable request identifier stored on the audit edge.
        idempotency_key: Client-supplied key for replay detection.
        session_scope: Opaque session identifier for outbound limit tracking.

    Returns:
        Dict containing request_id, amount, source_balance, destination_balance, and replayed flag.

    Raises:
        NodeNotFoundError: If player or counterparty character nodes are missing.
        CurrencyInsufficientFundsError: If source balance cannot cover the amount.
        CurrencyValidationError: If the transfer fails write-guard conditions.
    """
    source_id = player_id if action_type == "buy_item" else counterparty_id
    destination_id = counterparty_id if action_type == "buy_item" else player_id
    return await apply_currency_transfer(
        session=session,
        settings=settings,
        source_id=source_id,
        destination_id=destination_id,
        amount=amount,
        reason=reason,
        request_id=request_id,
        idempotency_key=idempotency_key,
        session_scope=session_scope,
        transfer_kind=action_type,
    )


async def apply_currency_transfer(
    *,
    session: AsyncSession,
    settings: Settings,
    source_id: str,
    destination_id: str,
    amount: int,
    reason: str,
    request_id: str,
    idempotency_key: str,
    session_scope: str,
    transfer_kind: str,
) -> dict[str, int | str | bool]:
    """Apply one validated currency transfer through the shared coordinator path.

    Args:
        session: Active Neo4j async session.
        settings: Application settings providing transfer bound configuration.
        source_id: ID of the debited character; "system" triggers reward path.
        destination_id: ID of the credited character.
        amount: Positive integer amount to transfer.
        reason: Human-readable description persisted on the audit edge.
        request_id: Stable request identifier stored on the audit edge.
        idempotency_key: Client-supplied key for replay detection.
        session_scope: Opaque session identifier for outbound limit tracking.
        transfer_kind: Transfer classification label persisted on the audit edge.

    Returns:
        Dict containing request_id, amount, source_balance, destination_balance, and replayed flag.

    Raises:
        NodeNotFoundError: If source or destination character nodes are missing.
        CurrencyInsufficientFundsError: If source balance cannot cover the amount.
        CurrencyValidationError: If the transfer fails write-guard conditions.
    """
    started_at = perf_counter()
    try:
        current_total = await get_outbound_session_total(
            session=session,
            source_id=source_id,
            session_scope=session_scope,
            transfer_kind=transfer_kind,
        )
        transfer_command = build_currency_transfer_command(
            settings=settings,
            source_id=source_id,
            destination_id=destination_id,
            amount=amount,
            reason=reason,
            session_scope=session_scope,
            transfer_kind=transfer_kind,
            current_session_total=current_total,
        )
        transfer_result = await transfer_currency_atomic(
            session=session,
            source_id=transfer_command.source_id,
            destination_id=transfer_command.destination_id,
            amount=transfer_command.amount,
            reason=transfer_command.reason,
            request_id=request_id,
            idempotency_key=idempotency_key,
            session_scope=transfer_command.session_scope,
            transfer_kind=transfer_command.transfer_kind,
        )
        increment_metric(
            metric=CURRENCY_TRANSFERS_METRIC,
            labels={"kind": transfer_kind.lower(), "result": "success"},
        )
        record_graph_write_metrics(operation="currency_transfer", result="success", started_at=started_at)
        return transfer_result.model_dump(mode="python")
    except Exception:
        increment_metric(
            metric=CURRENCY_TRANSFERS_METRIC,
            labels={"kind": transfer_kind.lower(), "result": "failure"},
        )
        record_graph_write_metrics(operation="currency_transfer", result="failure", started_at=started_at)
        raise


async def apply_item_transfer(
    *,
    session: AsyncSession,
    source_id: str,
    destination_id: str,
    item_id: str,
    quantity: int,
    reason: str,
    request_id: str,
    idempotency_key: str,
    transfer_kind: str,
) -> dict[str, str | int | bool]:
    """Apply one validated item transfer through the shared trading coordinator path.

    Args:
        session: Active Neo4j async session.
        source_id: ID of the character giving the item; "system" triggers grant path.
        destination_id: ID of the character receiving the item.
        item_id: Identifier of the item being transferred.
        quantity: Positive integer count of items.
        reason: Human-readable description persisted on the audit edge.
        request_id: Stable request identifier stored on the audit edge.
        idempotency_key: Client-supplied key for replay detection.
        transfer_kind: Transfer classification label persisted on the audit edge.

    Returns:
        Dict containing request_id, item_id, quantity, and replayed flag.

    Raises:
        NodeNotFoundError: If source or destination character nodes are missing.
        ItemTransferValidationError: If the item transfer fails write-guard conditions.
    """
    started_at = perf_counter()
    try:
        transfer_command = build_item_transfer_command(
            source_id=source_id,
            destination_id=destination_id,
            item_id=item_id,
            quantity=quantity,
            reason=reason,
            transfer_kind=transfer_kind,
        )
        transfer_result = await transfer_item_atomic(
            session=session,
            source_id=transfer_command.source_id,
            destination_id=transfer_command.destination_id,
            item_id=transfer_command.item_id,
            quantity=transfer_command.quantity,
            reason=transfer_command.reason,
            request_id=request_id,
            idempotency_key=idempotency_key,
            transfer_kind=transfer_command.transfer_kind,
        )
        record_graph_write_metrics(operation="item_transfer", result="success", started_at=started_at)
        return transfer_result.model_dump(mode="python")
    except Exception:
        record_graph_write_metrics(operation="item_transfer", result="failure", started_at=started_at)
        raise
