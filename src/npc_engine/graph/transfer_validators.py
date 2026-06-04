"""
transfer_validators.py - Validates currency and item transfer requests, returning immutable commands.
Layer: graph
Purpose: (auto-detected — review)

Does NOT: execute graph writes or open transactions.

Dependencies injected: Settings (for currency limits).
"""

from pydantic import BaseModel, ConfigDict, Field

from npc_engine.config import Settings
from npc_engine.utils.errors import CurrencyValidationError, ItemTransferValidationError


CURRENCY_ERR_AMOUNT_INVALID = "CURRENCY_AMOUNT_INVALID"
CURRENCY_ERR_SELF_TRANSFER = "CURRENCY_SELF_TRANSFER"
CURRENCY_ERR_PER_TRANSACTION_LIMIT = "CURRENCY_PER_TRANSACTION_LIMIT"
CURRENCY_ERR_PER_SESSION_LIMIT = "CURRENCY_PER_SESSION_LIMIT"


class CurrencyTransferCommand(BaseModel):
    """Validated transfer command for graph writer execution."""

    source_id: str
    destination_id: str
    amount: int
    reason: str
    session_scope: str
    transfer_kind: str

    model_config = ConfigDict(frozen=True)


class ItemTransferCommand(BaseModel):
    """Validated command payload for one item transfer write."""

    source_id: str
    destination_id: str
    item_id: str
    quantity: int = Field(ge=1)
    reason: str
    transfer_kind: str

    model_config = ConfigDict(frozen=True)


def build_currency_transfer_command(
    *,
    settings: Settings,
    source_id: str,
    destination_id: str,
    amount: int,
    reason: str,
    session_scope: str,
    transfer_kind: str,
    current_session_total: int,
) -> CurrencyTransferCommand:
    """Validate transfer bounds and return an immutable currency transfer command.

    Args:
        settings: Application settings providing per-transaction and per-session limits.
        source_id: ID of the character debited; use "system" for reward grants.
        destination_id: ID of the character credited.
        amount: Positive integer amount to transfer.
        reason: Human-readable description of the transfer.
        session_scope: Opaque session identifier used for per-session limit checks.
        transfer_kind: Transfer classification label (e.g. "buy_item", "quest_reward").
        current_session_total: Sum of outbound transfers already applied this session.

    Returns:
        Immutable CurrencyTransferCommand ready for the graph writer.

    Raises:
        CurrencyValidationError: If amount is non-positive, source equals destination,
            or any configured limit is exceeded.
    """
    if amount <= 0:
        raise CurrencyValidationError(
            code=CURRENCY_ERR_AMOUNT_INVALID,
            detail="Currency amount must be greater than zero.",
        )

    if source_id == destination_id:
        raise CurrencyValidationError(
            code=CURRENCY_ERR_SELF_TRANSFER,
            detail="Source and destination must differ for currency transfer.",
        )

    if amount > settings.CURRENCY_MAX_PER_TRANSACTION:
        raise CurrencyValidationError(
            code=CURRENCY_ERR_PER_TRANSACTION_LIMIT,
            detail=(
                "Requested amount exceeds per-transaction limit "
                f"({settings.CURRENCY_MAX_PER_TRANSACTION})."
            ),
        )

    if current_session_total + amount > settings.CURRENCY_MAX_PER_SESSION:
        raise CurrencyValidationError(
            code=CURRENCY_ERR_PER_SESSION_LIMIT,
            detail=(
                "Requested amount exceeds per-session limit "
                f"({settings.CURRENCY_MAX_PER_SESSION})."
            ),
        )

    return CurrencyTransferCommand(
        source_id=source_id,
        destination_id=destination_id,
        amount=amount,
        reason=reason,
        session_scope=session_scope,
        transfer_kind=transfer_kind,
    )


def build_item_transfer_command(
    *,
    source_id: str,
    destination_id: str,
    item_id: str,
    quantity: int,
    reason: str,
    transfer_kind: str,
) -> ItemTransferCommand:
    """Validate item transfer request and return an immutable command payload.

    Args:
        source_id: ID of the character giving the item; use "system" for reward grants.
        destination_id: ID of the character receiving the item.
        item_id: Non-empty identifier of the item being transferred.
        quantity: Positive integer count of items to transfer.
        reason: Human-readable description of the transfer.
        transfer_kind: Transfer classification label (e.g. "trade", "quest_reward").

    Returns:
        Immutable ItemTransferCommand ready for the graph writer.

    Raises:
        ItemTransferValidationError: If item_id is empty, quantity is non-positive,
            or source equals destination.
    """
    if item_id.strip() == "":
        raise ItemTransferValidationError(code="ITEM_ID_REQUIRED", detail="item_id cannot be empty")
    if quantity <= 0:
        raise ItemTransferValidationError(code="ITEM_QUANTITY_INVALID", detail="quantity must be greater than zero")
    if source_id == destination_id:
        raise ItemTransferValidationError(
            code="ITEM_SELF_TRANSFER",
            detail="Source and destination must differ for item transfer",
        )

    return ItemTransferCommand(
        source_id=source_id,
        destination_id=destination_id,
        item_id=item_id,
        quantity=quantity,
        reason=reason,
        transfer_kind=transfer_kind,
    )
