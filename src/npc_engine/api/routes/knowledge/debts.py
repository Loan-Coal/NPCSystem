"""
Module: debts
Layer: api
Purpose: Admin HTTP routes for creating and retrieving OWES obligation edges between Characters.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.owes_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.helpers import OkEnvelope, error_response, ok_response
from npc_engine.graph.owes_service import (
    create_debt,
    get_debts_for_character_svc,
    update_debt_status,
)
from npc_engine.utils.logging import get_logger

logger = get_logger(__name__)

_INVALID_DEBT_REQUEST = error_response(
    error_code="INVALID_REQUEST", message="Invalid request parameter."
)

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateDebtRequest(BaseModel):
    """Request body for creating an obligation from a debtor to a creditor."""

    creditor_id: str = Field(..., min_length=1)
    kind: str = Field(..., pattern=r"^(money|favor|item|service)$")
    magnitude: str = Field(..., min_length=1, max_length=256)
    due_by: str = Field(default="")

    model_config = ConfigDict(frozen=True)


class UpdateDebtStatusRequest(BaseModel):
    """Request body for updating the status of an obligation."""

    status: str = Field(..., pattern=r"^(pending|fulfilled|defaulted)$")

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/debts", tags=["debts"])


@router.post("/{debtor_id}", response_model=OkEnvelope[dict[str, Any]])
async def create_debt_for_character(
    debtor_id: str,
    body: CreateDebtRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create an OWES obligation from debtor to creditor.

    Args:
        debtor_id: ID of the character who owes.
        body: Creditor ID, kind, magnitude, and optional due_by.

    Returns:
        Envelope confirming creation.
    """
    try:
        await create_debt(
            session,
            debtor_id=debtor_id,
            creditor_id=body.creditor_id,
            kind=body.kind,
            magnitude=body.magnitude,
            due_by=body.due_by,
        )
    except ValueError as exc:
        logger.warning("debt_create_invalid", extra={"error": str(exc)})
        raise HTTPException(status_code=422, detail=_INVALID_DEBT_REQUEST) from exc
    return ok_response({"debtor_id": debtor_id, "creditor_id": body.creditor_id})


@router.get("/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def list_debts_for_character(
    character_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List pending obligations for a character (as debtor or creditor).

    Args:
        character_id: ID of the character.

    Returns:
        Envelope with list of obligation dicts ordered by due_by ascending.
    """
    debts = await get_debts_for_character_svc(session, character_id=character_id)
    return ok_response({"debts": debts})


@router.patch("/{debtor_id}/{creditor_id}", response_model=OkEnvelope[dict[str, Any]])
async def patch_debt_status(
    debtor_id: str,
    creditor_id: str,
    body: UpdateDebtStatusRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Update the status of an OWES obligation.

    Args:
        debtor_id: ID of the debtor character.
        creditor_id: ID of the creditor character.
        body: New status value.

    Returns:
        Envelope confirming the update.
    """
    try:
        await update_debt_status(
            session,
            debtor_id=debtor_id,
            creditor_id=creditor_id,
            status=body.status,
        )
    except ValueError as exc:
        logger.warning("debt_status_update_invalid", extra={"error": str(exc)})
        raise HTTPException(status_code=422, detail=_INVALID_DEBT_REQUEST) from exc
    return ok_response({"debtor_id": debtor_id, "creditor_id": creditor_id, "status": body.status})
