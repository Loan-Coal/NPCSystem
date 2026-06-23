"""
test_transfer_validators.py - Unit tests for currency and item transfer validators.

Does NOT: connect to Neo4j, Redis, or any external service.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from npc_engine.graph.infra.transfer_validators import (
    CURRENCY_ERR_AMOUNT_INVALID,
    CURRENCY_ERR_PER_SESSION_LIMIT,
    CURRENCY_ERR_PER_TRANSACTION_LIMIT,
    CURRENCY_ERR_SELF_TRANSFER,
    CurrencyTransferCommand,
    ItemTransferCommand,
    build_currency_transfer_command,
    build_item_transfer_command,
)
from npc_engine.utils.errors import CurrencyValidationError, ItemTransferValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(*, per_tx: int = 1000, per_session: int = 5000) -> MagicMock:
    settings = MagicMock()
    settings.CURRENCY_MAX_PER_TRANSACTION = per_tx
    settings.CURRENCY_MAX_PER_SESSION = per_session
    return settings


def _currency_cmd(**overrides):
    defaults = dict(
        settings=_make_settings(),
        source_id="char_a",
        destination_id="char_b",
        amount=100,
        reason="trade",
        session_scope="session_1",
        transfer_kind="buy_item",
        current_session_total=0,
    )
    defaults.update(overrides)
    return build_currency_transfer_command(**defaults)


# ---------------------------------------------------------------------------
# build_currency_transfer_command — happy path
# ---------------------------------------------------------------------------


def test_currency_happy_path_returns_command():
    cmd = _currency_cmd()
    assert isinstance(cmd, CurrencyTransferCommand)
    assert cmd.source_id == "char_a"
    assert cmd.destination_id == "char_b"
    assert cmd.amount == 100
    assert cmd.reason == "trade"
    assert cmd.session_scope == "session_1"
    assert cmd.transfer_kind == "buy_item"


def test_currency_command_is_frozen():
    cmd = _currency_cmd()
    with pytest.raises(Exception):
        cmd.amount = 999  # type: ignore[misc]


def test_currency_exact_per_transaction_limit_passes():
    cmd = _currency_cmd(settings=_make_settings(per_tx=200), amount=200)
    assert cmd.amount == 200


def test_currency_exact_per_session_limit_passes():
    cmd = _currency_cmd(
        settings=_make_settings(per_tx=300, per_session=500),
        amount=300,
        current_session_total=200,
    )
    assert cmd.amount == 300


# ---------------------------------------------------------------------------
# build_currency_transfer_command — validation errors
# ---------------------------------------------------------------------------


def test_currency_zero_amount_raises():
    with pytest.raises(CurrencyValidationError) as exc_info:
        _currency_cmd(amount=0)
    assert exc_info.value.code == CURRENCY_ERR_AMOUNT_INVALID


def test_currency_negative_amount_raises():
    with pytest.raises(CurrencyValidationError) as exc_info:
        _currency_cmd(amount=-50)
    assert exc_info.value.code == CURRENCY_ERR_AMOUNT_INVALID


def test_currency_self_transfer_raises():
    with pytest.raises(CurrencyValidationError) as exc_info:
        _currency_cmd(source_id="char_a", destination_id="char_a")
    assert exc_info.value.code == CURRENCY_ERR_SELF_TRANSFER


def test_currency_exceeds_per_transaction_limit_raises():
    with pytest.raises(CurrencyValidationError) as exc_info:
        _currency_cmd(settings=_make_settings(per_tx=99), amount=100)
    assert exc_info.value.code == CURRENCY_ERR_PER_TRANSACTION_LIMIT


def test_currency_exceeds_per_session_limit_raises():
    with pytest.raises(CurrencyValidationError) as exc_info:
        _currency_cmd(
            settings=_make_settings(per_tx=1000, per_session=500),
            amount=300,
            current_session_total=300,
        )
    assert exc_info.value.code == CURRENCY_ERR_PER_SESSION_LIMIT


def test_currency_error_detail_is_non_empty():
    with pytest.raises(CurrencyValidationError) as exc_info:
        _currency_cmd(amount=0)
    assert exc_info.value.detail != ""


@pytest.mark.parametrize("kind", ["buy_item", "quest_reward", "trade", "system_grant"])
def test_currency_various_transfer_kinds(kind: str):
    cmd = _currency_cmd(transfer_kind=kind)
    assert cmd.transfer_kind == kind


# ---------------------------------------------------------------------------
# build_item_transfer_command — happy path
# ---------------------------------------------------------------------------


def test_item_happy_path_returns_command():
    cmd = build_item_transfer_command(
        source_id="char_a",
        destination_id="char_b",
        item_id="sword_01",
        quantity=1,
        reason="quest reward",
        transfer_kind="quest_reward",
    )
    assert isinstance(cmd, ItemTransferCommand)
    assert cmd.item_id == "sword_01"
    assert cmd.quantity == 1


def test_item_command_is_frozen():
    cmd = build_item_transfer_command(
        source_id="char_a",
        destination_id="char_b",
        item_id="sword_01",
        quantity=1,
        reason="test",
        transfer_kind="trade",
    )
    with pytest.raises(Exception):
        cmd.quantity = 99  # type: ignore[misc]


def test_item_large_quantity_passes():
    cmd = build_item_transfer_command(
        source_id="char_a",
        destination_id="char_b",
        item_id="gold_coin",
        quantity=999,
        reason="bulk trade",
        transfer_kind="trade",
    )
    assert cmd.quantity == 999


# ---------------------------------------------------------------------------
# build_item_transfer_command — validation errors
# ---------------------------------------------------------------------------


def test_item_empty_item_id_raises():
    with pytest.raises(ItemTransferValidationError) as exc_info:
        build_item_transfer_command(
            source_id="char_a",
            destination_id="char_b",
            item_id="",
            quantity=1,
            reason="test",
            transfer_kind="trade",
        )
    assert exc_info.value.code == "ITEM_ID_REQUIRED"


def test_item_whitespace_only_item_id_raises():
    with pytest.raises(ItemTransferValidationError) as exc_info:
        build_item_transfer_command(
            source_id="char_a",
            destination_id="char_b",
            item_id="   ",
            quantity=1,
            reason="test",
            transfer_kind="trade",
        )
    assert exc_info.value.code == "ITEM_ID_REQUIRED"


def test_item_zero_quantity_raises():
    with pytest.raises(ItemTransferValidationError) as exc_info:
        build_item_transfer_command(
            source_id="char_a",
            destination_id="char_b",
            item_id="sword_01",
            quantity=0,
            reason="test",
            transfer_kind="trade",
        )
    assert exc_info.value.code == "ITEM_QUANTITY_INVALID"


def test_item_negative_quantity_raises():
    with pytest.raises(ItemTransferValidationError) as exc_info:
        build_item_transfer_command(
            source_id="char_a",
            destination_id="char_b",
            item_id="sword_01",
            quantity=-1,
            reason="test",
            transfer_kind="trade",
        )
    assert exc_info.value.code == "ITEM_QUANTITY_INVALID"


def test_item_self_transfer_raises():
    with pytest.raises(ItemTransferValidationError) as exc_info:
        build_item_transfer_command(
            source_id="char_a",
            destination_id="char_a",
            item_id="sword_01",
            quantity=1,
            reason="test",
            transfer_kind="trade",
        )
    assert exc_info.value.code == "ITEM_SELF_TRANSFER"
