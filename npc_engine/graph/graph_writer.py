"""
graph_writer.py - Transaction coordinator for graph mutation workflows.

Does NOT: define mutation policy bounds.

Dependencies injected: AsyncSession.
"""

import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Literal

from neo4j import AsyncSession

from config import Settings
from engines.economy.trading_engine import build_item_transfer_command
from engines.economy.currency_verification_engine import build_currency_transfer_command
from graph.delta_log_writer import write_delta_log
from graph.currency_writer import get_outbound_session_total, transfer_currency_atomic
from graph.item_writer import transfer_item_atomic
from graph.edge_schemas import RelationDeltaEntry
from graph.relation_writer import get_relation_values, set_relation_values
from mutation.delta_log_manager import append_delta
from mutation.modifier_bounds_validator import (
    DeltaValidationConfig,
    clamp_relation_values,
    validate_deltas,
)
from utils.errors import RelationEdgeNotFoundError
from utils.metrics import increment_metric, observe_metric


GRAPH_WRITES_METRIC = "graph_writes_total"
GRAPH_WRITE_LATENCY_METRIC = "graph_write_latency_seconds"
CURRENCY_TRANSFERS_METRIC = "currency_transfers_total"


def _record_graph_write_metrics(*, operation: str, result: str, started_at: float) -> None:
    """Record graph write count and latency with bounded operation labels."""

    labels = {"operation": operation, "result": result}
    increment_metric(metric=GRAPH_WRITES_METRIC, labels=labels)
    observe_metric(metric=GRAPH_WRITE_LATENCY_METRIC, value=perf_counter() - started_at, labels=labels)


async def apply_relation_delta(
    session: AsyncSession,
    settings: Settings,
    src_id: str,
    dst_id: str,
    deltas: dict[str, int],
    cause_id: str,
    tick_id: int,
) -> dict[str, int]:
    """Validate and atomically apply relation deltas for one directed edge."""

    started_at = perf_counter()

    config = DeltaValidationConfig(
        max_delta_per_turn=settings.MAX_RELATION_DELTA_PER_TURN,
        max_delta_per_window=settings.MAX_RELATION_DELTA_PER_WINDOW,
        relation_window_size=settings.RELATION_WINDOW_SIZE,
    )

    try:
        tx = await session.begin_transaction()
        async with tx:
            current = await get_relation_values(tx=tx, src_id=src_id, dst_id=dst_id)
            relation_result = await tx.run(
                "MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id}) "
                "RETURN coalesce(r.delta_log, '[]') AS delta_log",
                src_id=src_id,
                dst_id=dst_id,
            )
            relation_record = await relation_result.single()
            if relation_record is None:
                raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)
            raw_log = relation_record["delta_log"] if relation_record else "[]"
            parsed_log = json.loads(raw_log)

            canonical_log = []
            for entry in parsed_log:
                if "timestamp" not in entry or entry["timestamp"] is None:
                    entry = {
                        **entry,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                canonical_log.append(RelationDeltaEntry.model_validate(entry))
            validated = validate_deltas(
                proposed_deltas=deltas,
                delta_log=canonical_log,
                config=config,
            )
            clamped = clamp_relation_values(current_values=current, deltas=validated)
            await set_relation_values(tx=tx, src_id=src_id, dst_id=dst_id, new_values=clamped)

            new_delta_log = append_delta(
                delta_log=canonical_log,
                tick_id=tick_id,
                cause_id=cause_id,
                deltas=validated,
                max_entries=settings.RELATION_WINDOW_SIZE,
            )
            payload = [entry.model_dump(mode="json") for entry in new_delta_log]
            await write_delta_log(tx=tx, src_id=src_id, dst_id=dst_id, delta_log_payload=payload)
            await tx.commit()
            _record_graph_write_metrics(operation="relation_delta", result="success", started_at=started_at)
            return clamped
    except Exception:
        _record_graph_write_metrics(operation="relation_delta", result="failure", started_at=started_at)
        raise


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
    """Apply buy/sell currency mutation through one validated transaction path."""

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
    """Apply one validated currency transfer through the shared P2 coordinator path."""

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
        _record_graph_write_metrics(operation="currency_transfer", result="success", started_at=started_at)
        return transfer_result.model_dump(mode="python")
    except Exception:
        increment_metric(
            metric=CURRENCY_TRANSFERS_METRIC,
            labels={"kind": transfer_kind.lower(), "result": "failure"},
        )
        _record_graph_write_metrics(operation="currency_transfer", result="failure", started_at=started_at)
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
    """Apply one validated item transfer through the shared trading coordinator path."""

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
        _record_graph_write_metrics(operation="item_transfer", result="success", started_at=started_at)
        return transfer_result.model_dump(mode="python")
    except Exception:
        _record_graph_write_metrics(operation="item_transfer", result="failure", started_at=started_at)
        raise
