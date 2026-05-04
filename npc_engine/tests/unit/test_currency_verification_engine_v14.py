"""
test_currency_verification_engine_v14.py - Unit tests for P2 currency validation rules.

Does NOT: perform graph writes.

Dependencies injected: Settings only.
"""

import pytest

from config import Settings
from graph.transfer_validators import (
    CURRENCY_ERR_AMOUNT_INVALID,
    CURRENCY_ERR_PER_SESSION_LIMIT,
    CURRENCY_ERR_PER_TRANSACTION_LIMIT,
    build_currency_transfer_command,
)
from utils.errors import CurrencyValidationError


def _settings() -> Settings:
    return Settings(
        API_KEY_SECRET="local_dev_secret_change_this_2026",
        CURRENCY_MAX_PER_TRANSACTION=100,
        CURRENCY_MAX_PER_SESSION=200,
    )


def test_currency_transfer_rejects_non_positive_amount() -> None:
    with pytest.raises(CurrencyValidationError) as error:
        build_currency_transfer_command(
            settings=_settings(),
            source_id="player",
            destination_id="shop",
            amount=0,
            reason="buy",
            session_scope="s1",
            transfer_kind="buy_item",
            current_session_total=0,
        )

    assert error.value.code == CURRENCY_ERR_AMOUNT_INVALID


def test_currency_transfer_rejects_amount_above_per_transaction_limit() -> None:
    with pytest.raises(CurrencyValidationError) as error:
        build_currency_transfer_command(
            settings=_settings(),
            source_id="player",
            destination_id="shop",
            amount=101,
            reason="buy",
            session_scope="s1",
            transfer_kind="buy_item",
            current_session_total=0,
        )

    assert error.value.code == CURRENCY_ERR_PER_TRANSACTION_LIMIT


def test_currency_transfer_rejects_when_session_limit_would_be_exceeded() -> None:
    with pytest.raises(CurrencyValidationError) as error:
        build_currency_transfer_command(
            settings=_settings(),
            source_id="player",
            destination_id="shop",
            amount=25,
            reason="buy",
            session_scope="s1",
            transfer_kind="buy_item",
            current_session_total=180,
        )

    assert error.value.code == CURRENCY_ERR_PER_SESSION_LIMIT


def test_currency_transfer_returns_immutable_command_when_valid() -> None:
    command = build_currency_transfer_command(
        settings=_settings(),
        source_id="player",
        destination_id="shop",
        amount=25,
        reason="buy",
        session_scope="s1",
        transfer_kind="buy_item",
        current_session_total=100,
    )

    assert command.source_id == "player"
    assert command.destination_id == "shop"
    assert command.amount == 25
