"""
test_graph_writer_quest_reward_coordinator_v14.py - Unit tests for P3 quest reward graph coordinators.

Does NOT: execute real Neo4j writes.

Dependencies injected: monkeypatched coordinator collaborators.
"""

from __future__ import annotations

import pytest

pytest.importorskip("neo4j")

from config import Settings
from graph.transfer_validators import CurrencyTransferCommand, ItemTransferCommand
from graph.currency_writer import CurrencyTransferWriteResult
from graph.item_writer import ItemTransferWriteResult
from graph.graph_writer import apply_currency_transfer, apply_item_transfer


def _settings() -> Settings:
    return Settings(API_KEY_SECRET="local_dev_secret_change_this_2026")


@pytest.mark.asyncio
async def test_apply_currency_transfer_uses_validation_and_atomic_writer(monkeypatch) -> None:
    captured: dict[str, str | int] = {}

    async def fake_get_total(*, session, source_id: str, session_scope: str, transfer_kind: str) -> int:
        captured["source_for_total"] = source_id
        captured["transfer_kind_for_total"] = transfer_kind
        return 10

    def fake_build_command(**kwargs) -> CurrencyTransferCommand:
        captured["source"] = kwargs["source_id"]
        captured["destination"] = kwargs["destination_id"]
        captured["transfer_kind"] = kwargs["transfer_kind"]
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
            request_id=kwargs["request_id"],
            amount=kwargs["amount"],
            source_balance=40,
            destination_balance=60,
            replayed=False,
        )

    monkeypatch.setattr("graph.graph_writer.get_outbound_session_total", fake_get_total)
    monkeypatch.setattr("graph.graph_writer.build_currency_transfer_command", fake_build_command)
    monkeypatch.setattr("graph.graph_writer.transfer_currency_atomic", fake_transfer_atomic)

    result = await apply_currency_transfer(
        session=object(),  # type: ignore[arg-type]
        settings=_settings(),
        source_id="npc-1",
        destination_id="player-1",
        amount=25,
        reason="quest_reward",
        request_id="req-c1",
        idempotency_key="idem-c1",
        session_scope="s1",
        transfer_kind="quest_reward",
    )

    assert captured["source_for_total"] == "npc-1"
    assert captured["destination"] == "player-1"
    assert captured["transfer_kind"] == "quest_reward"
    assert result["amount"] == 25


@pytest.mark.asyncio
async def test_apply_item_transfer_uses_trading_command_and_atomic_writer(monkeypatch) -> None:
    captured: dict[str, str | int] = {}

    def fake_build_item_transfer_command(**kwargs) -> ItemTransferCommand:
        captured["source"] = kwargs["source_id"]
        captured["destination"] = kwargs["destination_id"]
        return ItemTransferCommand(
            source_id=kwargs["source_id"],
            destination_id=kwargs["destination_id"],
            item_id=kwargs["item_id"],
            quantity=kwargs["quantity"],
            reason=kwargs["reason"],
            transfer_kind=kwargs["transfer_kind"],
        )

    async def fake_transfer_item_atomic(**kwargs) -> ItemTransferWriteResult:
        captured["writer_item_id"] = kwargs["item_id"]
        return ItemTransferWriteResult(
            request_id=kwargs["request_id"],
            item_id=kwargs["item_id"],
            quantity=kwargs["quantity"],
            replayed=False,
        )

    monkeypatch.setattr("graph.graph_writer.build_item_transfer_command", fake_build_item_transfer_command)
    monkeypatch.setattr("graph.graph_writer.transfer_item_atomic", fake_transfer_item_atomic)

    result = await apply_item_transfer(
        session=object(),  # type: ignore[arg-type]
        source_id="npc-1",
        destination_id="player-1",
        item_id="item-1",
        quantity=2,
        reason="quest_reward",
        request_id="req-i1",
        idempotency_key="idem-i1",
        transfer_kind="quest_reward",
    )

    assert captured["source"] == "npc-1"
    assert captured["destination"] == "player-1"
    assert captured["writer_item_id"] == "item-1"
    assert result["quantity"] == 2
