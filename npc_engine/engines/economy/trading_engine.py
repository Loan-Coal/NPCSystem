"""
trading_engine.py - Validation and command shaping for item transfer operations.

Does NOT: execute graph writes.

Dependencies injected: None.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from utils.errors import ItemTransferValidationError


class ItemTransferCommand(BaseModel):
    """Validated command payload for one item transfer write."""

    source_id: str
    destination_id: str
    item_id: str
    quantity: int = Field(ge=1)
    reason: str
    transfer_kind: str

    model_config = ConfigDict(frozen=True)


def build_item_transfer_command(
    *,
    source_id: str,
    destination_id: str,
    item_id: str,
    quantity: int,
    reason: str,
    transfer_kind: str,
) -> ItemTransferCommand:
    """Validate item transfer request and return an immutable command payload."""

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
