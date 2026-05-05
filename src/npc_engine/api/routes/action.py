"""
action.py - Endpoint to report player actions against NPCs.

Does NOT: execute world tick logic.

Dependencies injected: AsyncSession, Settings.
"""

from datetime import datetime, timezone
from typing import Literal, cast

from fastapi import APIRouter, Depends, Request
from neo4j import AsyncSession

from npc_engine.api.action_helpers import (
    has_valid_currency_payload,
    is_currency_action,
    relation_deltas_for_action,
    resolve_currency_reason,
    resolve_request_id,
    resolve_session_scope,
)
from npc_engine.api.dependencies import get_db_session
from npc_engine.api.schemas import ActionReportRequest
from npc_engine.config import Settings, get_settings
from npc_engine.graph.graph_writer import apply_buy_sell_currency_transfer, apply_relation_delta
from npc_engine.utils.errors import CurrencyInsufficientFundsError, CurrencyValidationError, NodeNotFoundError, RelationEdgeNotFoundError


router = APIRouter()


@router.post("/action")
async def report_action(
    payload: ActionReportRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Apply a conservative relation delta for a reported gameplay action."""

    if is_currency_action(payload.action_type):
        currency_action_type = cast(Literal["buy_item", "sell_item"], payload.action_type)
        if not has_valid_currency_payload(payload.counterparty_id, payload.currency_amount):
            return {"status": "ignored", "reason": "currency_payload_invalid"}

        request_id = resolve_request_id(
            provided_request_id=http_request.headers.get("X-Request-ID", ""),
            action_type=payload.action_type,
            player_id=payload.player_id,
            counterparty_id=cast(str, payload.counterparty_id),
        )
        session_scope = resolve_session_scope(
            session_scope=payload.session_scope,
            player_id=payload.player_id,
            npc_id=payload.npc_id,
        )
        idempotency_key = http_request.headers.get(settings.IDEMPOTENCY_HEADER_NAME, "").strip()
        reason = resolve_currency_reason(action_type=payload.action_type, currency_reason=payload.currency_reason)

        try:
            transfer_result = await apply_buy_sell_currency_transfer(
                session=session,
                settings=settings,
                player_id=payload.player_id,
                counterparty_id=payload.counterparty_id,
                action_type=currency_action_type,
                amount=payload.currency_amount,
                reason=reason,
                request_id=request_id,
                idempotency_key=idempotency_key,
                session_scope=session_scope,
            )
        except CurrencyValidationError as error:
            return {
                "status": "ignored",
                "reason": "currency_validation_failed",
                "error_code": error.code,
            }
        except CurrencyInsufficientFundsError:
            return {"status": "ignored", "reason": "insufficient_funds"}
        except NodeNotFoundError:
            return {"status": "ignored", "reason": "character_missing"}

        return {"status": "ok", "currency_transfer": transfer_result}

    deltas = relation_deltas_for_action(action_type=payload.action_type, intensity=payload.intensity)
    try:
        await apply_relation_delta(
            session=session,
            settings=settings,
            src_id=payload.npc_id,
            dst_id=payload.player_id,
            deltas=deltas,
            cause_id=f"action:{payload.action_type}",
            tick_id=int(datetime.now(timezone.utc).timestamp()),
        )
    except RelationEdgeNotFoundError:
        return {"status": "ignored", "reason": "relation_missing"}
    return {"status": "ok", "applied_deltas": deltas}
