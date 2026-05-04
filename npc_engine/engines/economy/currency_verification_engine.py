"""
currency_verification_engine.py - Re-exports currency transfer validator from graph.transfer_validators.

Does NOT: perform graph writes.

Dependencies injected: Settings.
"""

# Validator and command class have moved to graph/transfer_validators.py (V1 fix).
# This module re-exports them so existing callers outside graph/ are unaffected
# until service #13 cleans up engines/economy/.
from graph.transfer_validators import (
    CURRENCY_ERR_AMOUNT_INVALID,
    CURRENCY_ERR_PER_SESSION_LIMIT,
    CURRENCY_ERR_PER_TRANSACTION_LIMIT,
    CURRENCY_ERR_SELF_TRANSFER,
    CurrencyTransferCommand,
    build_currency_transfer_command,
)

__all__ = [
    "CURRENCY_ERR_AMOUNT_INVALID",
    "CURRENCY_ERR_SELF_TRANSFER",
    "CURRENCY_ERR_PER_TRANSACTION_LIMIT",
    "CURRENCY_ERR_PER_SESSION_LIMIT",
    "CurrencyTransferCommand",
    "build_currency_transfer_command",
]
