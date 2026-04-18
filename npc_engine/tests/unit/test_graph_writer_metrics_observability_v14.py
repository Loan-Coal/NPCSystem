"""
test_graph_writer_metrics_observability_v14.py - Tests graph writer observability metrics.

Does NOT: execute real Neo4j writes.

Dependencies injected: Monkeypatched graph writer dependencies.
"""

import pytest

from config import Settings
from graph import graph_writer
from utils.metrics import get_counter_value, reset_metrics_registry


def setup_function() -> None:
    reset_metrics_registry()


@pytest.mark.asyncio
async def test_currency_transfer_emits_graph_and_currency_metrics(monkeypatch) -> None:
    """Currency coordinator should emit graph write and currency transfer counters."""

    async def fake_get_total(**kwargs):
        return 0

    def fake_build_command(**kwargs):
        return type(
            "Command",
            (),
            {
                "source_id": kwargs["source_id"],
                "destination_id": kwargs["destination_id"],
                "amount": kwargs["amount"],
                "reason": kwargs["reason"],
                "session_scope": kwargs["session_scope"],
                "transfer_kind": kwargs["transfer_kind"],
            },
        )()

    async def fake_transfer_currency_atomic(**kwargs):
        return type("Result", (), {"model_dump": lambda self, mode: {"amount": kwargs["amount"]}})()

    monkeypatch.setattr(graph_writer, "get_outbound_session_total", fake_get_total)
    monkeypatch.setattr(graph_writer, "build_currency_transfer_command", fake_build_command)
    monkeypatch.setattr(graph_writer, "transfer_currency_atomic", fake_transfer_currency_atomic)

    settings = Settings(API_KEY_SECRET="npc_dev_secret_2026_alpha")

    result = await graph_writer.apply_currency_transfer(
        session=None,  # type: ignore[arg-type]
        settings=settings,
        source_id="npc_1",
        destination_id="npc_2",
        amount=10,
        reason="test",
        request_id="req-1",
        idempotency_key="idemp-1",
        session_scope="scope-1",
        transfer_kind="buy_item",
    )

    graph_writes = get_counter_value(
        "graph_writes_total", labels={"operation": "currency_transfer", "result": "success"}
    )
    transfers = get_counter_value("currency_transfers_total", labels={"kind": "buy_item", "result": "success"})

    assert result["amount"] == 10
    assert graph_writes == 1.0
    assert transfers == 1.0


@pytest.mark.asyncio
async def test_currency_transfer_prevalidation_failure_emits_failure_metrics(monkeypatch) -> None:
    """Validation failures before atomic write should still emit failure counters."""

    async def fake_get_total(**kwargs):
        return 0

    def failing_build_command(**kwargs):
        raise ValueError("invalid transfer")

    monkeypatch.setattr(graph_writer, "get_outbound_session_total", fake_get_total)
    monkeypatch.setattr(graph_writer, "build_currency_transfer_command", failing_build_command)

    settings = Settings(API_KEY_SECRET="npc_dev_secret_2026_alpha")

    with pytest.raises(ValueError):
        await graph_writer.apply_currency_transfer(
            session=None,  # type: ignore[arg-type]
            settings=settings,
            source_id="npc_1",
            destination_id="npc_2",
            amount=10,
            reason="test",
            request_id="req-1",
            idempotency_key="idemp-1",
            session_scope="scope-1",
            transfer_kind="buy_item",
        )

    graph_writes = get_counter_value(
        "graph_writes_total", labels={"operation": "currency_transfer", "result": "failure"}
    )
    transfers = get_counter_value("currency_transfers_total", labels={"kind": "buy_item", "result": "failure"})

    assert graph_writes == 1.0
    assert transfers == 1.0
