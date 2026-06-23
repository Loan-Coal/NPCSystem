"""
Tests for graph.treaty_service.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.political.treaty_service import (
    TreatyCondition,
    break_treaty,
    check_treaty_conditions_mechanical,
    check_tribute_payment,
    create_treaty,
    expire_treaty,
    get_active_treaties_svc,
    get_expiring_treaties_svc,
)


# ---------------------------------------------------------------------------
# TreatyCondition model
# ---------------------------------------------------------------------------


def test_treaty_condition_model_valid() -> None:
    cond = TreatyCondition(type="no_attack")
    assert cond.type == "no_attack"
    assert cond.target_faction_id is None


def test_treaty_condition_model_tribute() -> None:
    cond = TreatyCondition(type="tribute", amount=100, interval_ticks=10)
    assert cond.amount == 100
    assert cond.interval_ticks == 10


# ---------------------------------------------------------------------------
# create_treaty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_treaty_returns_uuid_string() -> None:
    session = AsyncMock()
    treaty_id = await create_treaty(
        session,
        parties=["faction-a", "faction-b"],
        terms_narrative="Peace treaty",
        terms_conditions=[],
        signed_at_tick=5,
    )
    assert isinstance(treaty_id, str)
    assert len(treaty_id) > 0


@pytest.mark.asyncio
async def test_create_treaty_calls_run_for_node_and_each_party() -> None:
    session = AsyncMock()
    await create_treaty(
        session,
        parties=["faction-a", "faction-b"],
        terms_narrative="Alliance",
        terms_conditions=[TreatyCondition(type="no_attack")],
        signed_at_tick=10,
    )
    # 1 call for the Treaty node + 2 calls for BOUND_BY edges
    assert session.run.call_count == 3


@pytest.mark.asyncio
async def test_create_treaty_serializes_conditions_as_json() -> None:
    session = AsyncMock()
    conditions = [TreatyCondition(type="tribute", amount=50, interval_ticks=5)]
    await create_treaty(
        session,
        parties=["faction-a", "faction-b"],
        terms_narrative="Tribute pact",
        terms_conditions=conditions,
        signed_at_tick=1,
    )
    first_call_kwargs = session.run.call_args_list[0][1]
    parsed = json.loads(first_call_kwargs["terms_conditions"])
    assert parsed[0]["type"] == "tribute"
    assert parsed[0]["amount"] == 50


@pytest.mark.asyncio
async def test_create_treaty_passes_optional_fields() -> None:
    session = AsyncMock()
    await create_treaty(
        session,
        parties=["faction-a", "faction-b"],
        terms_narrative="Expiring pact",
        terms_conditions=[],
        signed_at_tick=1,
        expires_at_tick=100,
        binding_event_id="evt-7",
    )
    first_call_kwargs = session.run.call_args_list[0][1]
    assert first_call_kwargs["expires_at_tick"] == 100
    assert first_call_kwargs["binding_event_id"] == "evt-7"


# ---------------------------------------------------------------------------
# get_active_treaties_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_treaties_svc_delegates() -> None:
    expected = [{"id": "t-1", "status": "active"}]
    with patch(
        "npc_engine.graph.political.treaty_service.get_active_treaties",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_active_treaties_svc(session, "faction-a")
        mock_fn.assert_called_once_with(session, faction_id="faction-a")
        assert result == expected


# ---------------------------------------------------------------------------
# expire_treaty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expire_treaty_sets_status_expired() -> None:
    session = AsyncMock()
    await expire_treaty(session, "treaty-1", 99)
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["treaty_id"] == "treaty-1"
    assert kwargs["status"] == "expired"


# ---------------------------------------------------------------------------
# break_treaty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_break_treaty_sets_status_broken() -> None:
    session = AsyncMock()
    await break_treaty(session, treaty_id="treaty-1", breaking_faction_id="faction-a", tick=50)
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["treaty_id"] == "treaty-1"
    assert kwargs["status"] == "broken"


# ---------------------------------------------------------------------------
# check_treaty_conditions_mechanical
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_conditions_returns_empty_when_no_tribute_due() -> None:
    session = AsyncMock()
    conditions = [TreatyCondition(type="no_attack")]
    conditions_json = json.dumps([c.model_dump() for c in conditions])
    with patch(
        "npc_engine.graph.political.treaty_service.get_treaty_conditions",
        new_callable=AsyncMock,
        return_value=conditions_json,
    ):
        result = await check_treaty_conditions_mechanical(session, "treaty-1", tick=5)
        assert result == []


@pytest.mark.asyncio
async def test_check_conditions_returns_violation_when_tribute_unpayable() -> None:
    session = AsyncMock()
    conditions = [TreatyCondition(type="tribute", amount=100, interval_ticks=5, target_faction_id="faction-b")]
    conditions_json = json.dumps([c.model_dump() for c in conditions])
    with patch(
        "npc_engine.graph.political.treaty_service.get_treaty_conditions",
        new_callable=AsyncMock,
        return_value=conditions_json,
    ), patch(
        "npc_engine.graph.political.treaty_service.get_treaty_parties",
        new_callable=AsyncMock,
        return_value=["faction-a", "faction-b"],
    ), patch(
        "npc_engine.graph.political.treaty_service.check_tribute_payment",
        new_callable=AsyncMock,
        return_value=(False, "tribute unpaid: treasury 0 < required 100"),
    ):
        result = await check_treaty_conditions_mechanical(session, "treaty-1", tick=10)
        assert len(result) == 1
        assert "tribute" in result[0]


@pytest.mark.asyncio
async def test_check_conditions_returns_violation_when_treaty_not_found() -> None:
    session = AsyncMock()
    with patch(
        "npc_engine.graph.political.treaty_service.get_treaty_conditions",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await check_treaty_conditions_mechanical(session, "treaty-missing", tick=5)
        assert len(result) == 1
        assert "not found" in result[0]


# ---------------------------------------------------------------------------
# check_tribute_payment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_tribute_payment_returns_paid_when_treasury_sufficient() -> None:
    session = AsyncMock()
    with patch(
        "npc_engine.graph.political.treaty_service.get_faction_treasury",
        new_callable=AsyncMock,
        return_value=200,
    ), patch(
        "npc_engine.graph.political.treaty_service.deduct_faction_treasury",
        new_callable=AsyncMock,
    ) as mock_deduct:
        paid, msg = await check_tribute_payment(
            session, treaty_id="t-1", payer_faction_id="faction-a", amount=100
        )
        assert paid is True
        assert msg is None
        mock_deduct.assert_called_once_with(session, faction_id="faction-a", amount=100)


@pytest.mark.asyncio
async def test_check_tribute_payment_returns_violation_when_treasury_insufficient() -> None:
    session = AsyncMock()
    with patch(
        "npc_engine.graph.political.treaty_service.get_faction_treasury",
        new_callable=AsyncMock,
        return_value=50,
    ), patch(
        "npc_engine.graph.political.treaty_service.deduct_faction_treasury",
        new_callable=AsyncMock,
    ) as mock_deduct:
        paid, msg = await check_tribute_payment(
            session, treaty_id="t-1", payer_faction_id="faction-a", amount=100
        )
        assert paid is False
        assert msg is not None
        assert "treasury" in msg
        assert "100" in msg
        mock_deduct.assert_not_called()


@pytest.mark.asyncio
async def test_check_tribute_payment_exact_balance_succeeds() -> None:
    session = AsyncMock()
    with patch(
        "npc_engine.graph.political.treaty_service.get_faction_treasury",
        new_callable=AsyncMock,
        return_value=100,
    ), patch(
        "npc_engine.graph.political.treaty_service.deduct_faction_treasury",
        new_callable=AsyncMock,
    ) as mock_deduct:
        paid, msg = await check_tribute_payment(
            session, treaty_id="t-2", payer_faction_id="faction-a", amount=100
        )
        assert paid is True
        assert msg is None
        mock_deduct.assert_called_once()


# check_treaty_conditions_mechanical — with tribute paid (no violation)


@pytest.mark.asyncio
async def test_check_conditions_no_violation_when_tribute_paid() -> None:
    session = AsyncMock()
    conditions = [TreatyCondition(type="tribute", amount=50, interval_ticks=5, target_faction_id="faction-b")]
    conditions_json = json.dumps([c.model_dump() for c in conditions])
    with patch(
        "npc_engine.graph.political.treaty_service.get_treaty_conditions",
        new_callable=AsyncMock,
        return_value=conditions_json,
    ), patch(
        "npc_engine.graph.political.treaty_service.get_treaty_parties",
        new_callable=AsyncMock,
        return_value=["faction-a", "faction-b"],
    ), patch(
        "npc_engine.graph.political.treaty_service.check_tribute_payment",
        new_callable=AsyncMock,
        return_value=(True, None),
    ):
        result = await check_treaty_conditions_mechanical(session, "treaty-1", tick=10)
        assert result == []


@pytest.mark.asyncio
async def test_check_conditions_no_violation_when_tick_not_due() -> None:
    session = AsyncMock()
    conditions = [TreatyCondition(type="tribute", amount=100, interval_ticks=5, target_faction_id="faction-b")]
    conditions_json = json.dumps([c.model_dump() for c in conditions])
    with patch(
        "npc_engine.graph.political.treaty_service.get_treaty_conditions",
        new_callable=AsyncMock,
        return_value=conditions_json,
    ), patch(
        "npc_engine.graph.political.treaty_service.get_treaty_parties",
        new_callable=AsyncMock,
        return_value=["faction-a", "faction-b"],
    ):
        # tick=7 is not divisible by 5
        result = await check_treaty_conditions_mechanical(session, "treaty-1", tick=7)
        assert result == []


@pytest.mark.asyncio
async def test_check_conditions_violation_when_no_payer_found() -> None:
    session = AsyncMock()
    # target_faction_id matches the only party → no payer left
    conditions = [TreatyCondition(type="tribute", amount=100, interval_ticks=5, target_faction_id="faction-a")]
    conditions_json = json.dumps([c.model_dump() for c in conditions])
    with patch(
        "npc_engine.graph.political.treaty_service.get_treaty_conditions",
        new_callable=AsyncMock,
        return_value=conditions_json,
    ), patch(
        "npc_engine.graph.political.treaty_service.get_treaty_parties",
        new_callable=AsyncMock,
        return_value=["faction-a"],
    ):
        result = await check_treaty_conditions_mechanical(session, "treaty-1", tick=10)
        assert len(result) == 1
        assert "payer" in result[0]


# ---------------------------------------------------------------------------
# get_expiring_treaties_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_expiring_treaties_svc_delegates() -> None:
    expected = ["treaty-1", "treaty-2"]
    with patch(
        "npc_engine.graph.political.treaty_service.get_expiring_treaties",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_expiring_treaties_svc(session, tick_id=99)
        mock_fn.assert_called_once_with(session, tick_id=99)
        assert result == expected
