"""
test_graph_writer_currency_coordinator_v14.py - Unit tests for P2 buy/sell currency coordinator path.

Does NOT: execute real Neo4j writes.

Dependencies injected: monkeypatched coordinator collaborators.
"""

from __future__ import annotations

import pytest

pytest.importorskip("neo4j")

from config import Settings
from engines.economy.currency_verification_engine import CurrencyTransferCommand
from graph.currency_writer import CurrencyTransferWriteResult
from graph.graph_writer import apply_buy_sell_currency_transfer
from utils.errors import CurrencyValidationError


def _settings() -> Settings:
    return Settings(API_KEY_SECRET="local_dev_secret_change_this_2026")


@pytest.mark.asyncio
async def test_buy_transfer_routes_through_single_coordinator_path(monkeypatch) -> None:
    captured: dict[str, str | int] = {}

    async def fake_get_total(*, session, source_id: str, session_scope: str, transfer_kind: str) -> int:
        captured["source_for_total"] = source_id
        return 20

    def fake_build_command(**kwargs) -> CurrencyTransferCommand:
        captured["source"] = kwargs["source_id"]
        captured["destination"] = kwargs["destination_id"]
        return CurrencyTransferCommand(
            source_id=kwargs["source_id"],
            destination_id=kwargs["destination_id"],
            amount=kwargs["amount"],
            reason=kwargs["reason"],
            session_scope=kwargs["session_scope"],
            transfer_kind=kwargs["transfer_kind"],
        )

    async def fake_transfer_atomic(**kwargs) -> CurrencyTransferWriteResult:
        captured["writer_source"] = kwargs["source_id"]
        captured["writer_destination"] = kwargs["destination_id"]
        return CurrencyTransferWriteResult(
            request_id="req-1",
            amount=kwargs["amount"],
            source_balance=10,
            destination_balance=90,
            replayed=False,
        )

    monkeypatch.setattr("graph.graph_writer.get_outbound_session_total", fake_get_total)
    monkeypatch.setattr("graph.graph_writer.build_currency_transfer_command", fake_build_command)
    monkeypatch.setattr("graph.graph_writer.transfer_currency_atomic", fake_transfer_atomic)

    result = await apply_buy_sell_currency_transfer(
        session=object(),  # type: ignore[arg-type]
        settings=_settings(),
        player_id="player",
        counterparty_id="shop",
        action_type="buy_item",
        amount=15,
        reason="buy",
        request_id="req-1",
        idempotency_key="idem-1",
        session_scope="s1",
    )

    assert captured["source"] == "player"
    assert captured["destination"] == "shop"
    assert captured["writer_source"] == "player"
    assert captured["writer_destination"] == "shop"
    assert result["amount"] == 15


@pytest.mark.asyncio
async def test_sell_transfer_routes_through_single_coordinator_path(monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def fake_get_total(*, session, source_id: str, session_scope: str, transfer_kind: str) -> int:
        return 20

    def fake_build_command(**kwargs) -> CurrencyTransferCommand:
        captured["source"] = kwargs["source_id"]
        captured["destination"] = kwargs["destination_id"]
        return CurrencyTransferCommand(
            source_id=kwargs["source_id"],
            destination_id=kwargs["destination_id"],
            amount=kwargs["amount"],
            reason=kwargs["reason"],
            session_scope=kwargs["session_scope"],
            transfer_kind=kwargs["transfer_kind"],
        )

    async def fake_transfer_atomic(**kwargs) -> CurrencyTransferWriteResult:
        return CurrencyTransferWriteResult(
            request_id="req-2",
            amount=kwargs["amount"],
            source_balance=80,
            destination_balance=20,
            replayed=False,
        )

    monkeypatch.setattr("graph.graph_writer.get_outbound_session_total", fake_get_total)
    monkeypatch.setattr("graph.graph_writer.build_currency_transfer_command", fake_build_command)
    monkeypatch.setattr("graph.graph_writer.transfer_currency_atomic", fake_transfer_atomic)

    await apply_buy_sell_currency_transfer(
        session=object(),  # type: ignore[arg-type]
        settings=_settings(),
        player_id="player",
        counterparty_id="shop",
        action_type="sell_item",
        amount=15,
        reason="sell",
        request_id="req-2",
        idempotency_key="idem-1",
        session_scope="s1",
    )

    assert captured["source"] == "shop"
    assert captured["destination"] == "player"


@pytest.mark.asyncio
async def test_buy_sell_coordinator_stops_before_writer_when_validation_fails(monkeypatch) -> None:
    writer_called = {"value": False}

    async def fake_get_total(*, session, source_id: str, session_scope: str, transfer_kind: str) -> int:
        return 0

    def fake_build_command(**kwargs) -> CurrencyTransferCommand:
        raise CurrencyValidationError(code="CURRENCY_PER_TRANSACTION_LIMIT", detail="too much")

    async def fake_transfer_atomic(**kwargs) -> CurrencyTransferWriteResult:
        writer_called["value"] = True
        return CurrencyTransferWriteResult(
            request_id="req-3",
            amount=1,
            source_balance=0,
            destination_balance=0,
            replayed=False,
        )

    monkeypatch.setattr("graph.graph_writer.get_outbound_session_total", fake_get_total)
    monkeypatch.setattr("graph.graph_writer.build_currency_transfer_command", fake_build_command)
    monkeypatch.setattr("graph.graph_writer.transfer_currency_atomic", fake_transfer_atomic)

    with pytest.raises(CurrencyValidationError):
        await apply_buy_sell_currency_transfer(
            session=object(),  # type: ignore[arg-type]
            settings=_settings(),
            player_id="player",
            counterparty_id="shop",
            action_type="buy_item",
            amount=999,
            reason="buy",
            request_id="req-3",
            idempotency_key="idem-1",
            session_scope="s1",
        )

    assert writer_called["value"] is False
