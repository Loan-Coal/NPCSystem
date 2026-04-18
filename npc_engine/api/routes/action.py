"""
action.py - Endpoint to report player actions against NPCs.

Does NOT: execute world tick logic.

Dependencies injected: AsyncSession, Settings.
"""

from datetime import datetime, timezone
from typing import Literal, cast

from fastapi import APIRouter, Depends, Request
from neo4j import AsyncSession

from api.dependencies import get_db_session
from api.schemas import ActionReportRequest
from config import Settings, get_settings
from graph.graph_writer import apply_buy_sell_currency_transfer, apply_relation_delta
from utils.errors import CurrencyInsufficientFundsError, CurrencyValidationError, NodeNotFoundError, RelationEdgeNotFoundError


router = APIRouter()


@router.post("/action")
async def report_action(
    payload: ActionReportRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Apply a conservative relation delta for a reported gameplay action."""

    if payload.action_type in {"buy_item", "sell_item"}:
        currency_action_type = cast(Literal["buy_item", "sell_item"], payload.action_type)
        if payload.counterparty_id is None or payload.currency_amount is None:
            return {"status": "ignored", "reason": "currency_payload_invalid"}

        request_id = http_request.headers.get("X-Request-ID", "").strip()
        if request_id == "":
            request_id = (
                f"action:{payload.action_type}:"
                f"{payload.player_id}:{payload.counterparty_id}:{int(datetime.now(timezone.utc).timestamp())}"
            )

        session_scope = payload.session_scope or f"{payload.player_id}:{payload.npc_id}"
        idempotency_key = http_request.headers.get(settings.IDEMPOTENCY_HEADER_NAME, "").strip()
        reason = payload.currency_reason or f"action:{payload.action_type}"

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

    delta = min(15, max(-15, payload.intensity // 10))
    deltas = {"trust": 0, "fear": 0, "affection": 0}
    if payload.action_type == "help":
        deltas = {"trust": delta, "fear": -delta, "affection": delta}
    if payload.action_type == "attack":
        deltas = {"trust": -delta, "fear": delta, "affection": -delta}
    if payload.action_type == "give_item":
        deltas = {"trust": delta, "fear": 0, "affection": delta}
    if payload.action_type == "steal":
        deltas = {"trust": -delta, "fear": delta, "affection": -delta}
    if payload.action_type == "observe":
        deltas = {"trust": 0, "fear": 0, "affection": 0}
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
