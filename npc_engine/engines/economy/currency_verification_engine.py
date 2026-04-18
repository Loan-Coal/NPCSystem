"""
currency_verification_engine.py - Validates currency transfer intent against v1.4 limits.

Does NOT: perform graph writes.

Dependencies injected: Settings.
"""

from pydantic import BaseModel, ConfigDict

from config import Settings
from utils.errors import CurrencyValidationError


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
    """Validate transfer bounds and return immutable command payload."""

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
