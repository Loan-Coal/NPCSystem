"""
Tests for graph.pledge_service and context integration for pledges.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from npc_engine.graph.pledge_service import (
    break_pledge,
    create_pledge,
    get_pledges_for_character_svc,
    get_expiring_pledges_svc,
)
from npc_engine.graph.pledge_violation_service import check_pledge_violations


# ---------------------------------------------------------------------------
# create_pledge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pledge_calls_session_run_with_required_fields() -> None:
    session = AsyncMock()
    await create_pledge(
        session,
        pledger_id="char-1",
        pledgee_id="char-2",
        pledge_type="protect",
        tick=10,
    )
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["pledger_id"] == "char-1"
    assert kwargs["pledgee_id"] == "char-2"
    assert kwargs["pledge_type"] == "protect"
    assert kwargs["sworn_at_tick"] == 10
    assert kwargs["expires_at_tick"] is None
    assert kwargs["severity"] == 50


@pytest.mark.asyncio
async def test_create_pledge_passes_optional_fields() -> None:
    session = AsyncMock()
    await create_pledge(
        session,
        pledger_id="char-1",
        pledgee_id="char-2",
        pledge_type="fealty",
        tick=5,
        expires_at_tick=100,
        witness_id="char-3",
        binding_event_id="evt-42",
        severity=80,
    )
    _, kwargs = session.run.call_args
    assert kwargs["expires_at_tick"] == 100
    assert kwargs["witness_character_id"] == "char-3"
    assert kwargs["binding_event_id"] == "evt-42"
    assert kwargs["severity"] == 80


# ---------------------------------------------------------------------------
# get_pledges_for_character_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pledges_for_character_svc_delegates() -> None:
    expected = [{"pledger_id": "char-1", "pledge_type": "protect", "is_active": True}]
    with patch(
        "npc_engine.graph.pledge_service.get_pledges_for_character",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_pledges_for_character_svc(session, "char-1")
        mock_fn.assert_called_once_with(session, character_id="char-1", active_only=True)
        assert result == expected


@pytest.mark.asyncio
async def test_get_pledges_for_character_svc_passes_active_only_false() -> None:
    with patch(
        "npc_engine.graph.pledge_service.get_pledges_for_character",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_fn:
        session = AsyncMock()
        await get_pledges_for_character_svc(session, "char-1", active_only=False)
        mock_fn.assert_called_once_with(session, character_id="char-1", active_only=False)


# ---------------------------------------------------------------------------
# check_pledge_violations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_pledge_violations_returns_empty_list_when_no_pledges() -> None:
    """No active pledges → empty violations list."""
    from unittest.mock import patch

    session = AsyncMock()
    with patch(
        "npc_engine.graph.pledge_violation_service.get_active_pledges_for_pledger",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await check_pledge_violations(session, pledger_id="char-1", tick=5)
    assert result == []


# ---------------------------------------------------------------------------
# break_pledge — trust drop and faction swing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_break_pledge_deactivates_pledge() -> None:
    session = AsyncMock()
    # Mock faction lookup returning None (no faction)
    no_faction_result = AsyncMock()
    no_faction_result.single = AsyncMock(return_value=None)
    session.run.return_value = no_faction_result

    await break_pledge(
        session,
        pledger_id="char-1",
        pledgee_id="char-2",
        pledge_type="protect",
        tick=20,
    )
    # Should have called run at least once (deactivate + trust drops)
    assert session.run.call_count >= 1


@pytest.mark.asyncio
async def test_break_pledge_applies_trust_drop_both_directions() -> None:
    session = AsyncMock()
    calls_made = []

    async def mock_run(query, **kwargs):
        calls_made.append((query, kwargs))
        result = AsyncMock()
        result.single = AsyncMock(return_value=None)
        return result

    session.run = mock_run

    await break_pledge(
        session,
        pledger_id="char-1",
        pledgee_id="char-2",
        pledge_type="protect",
        tick=20,
    )

    # Verify trust drop queries were called in both directions
    trust_drop_calls = [
        kwargs for _, kwargs in calls_made
        if "src_id" in kwargs and "drop" in kwargs
    ]
    src_ids = {c["src_id"] for c in trust_drop_calls}
    assert "char-1" in src_ids
    assert "char-2" in src_ids


@pytest.mark.asyncio
async def test_break_pledge_applies_faction_swing_when_different_factions() -> None:
    session = AsyncMock()
    calls_made = []

    faction_for = {"char-1": "faction-a", "char-2": "faction-b"}

    async def mock_run(query, **kwargs):
        calls_made.append((query, kwargs))
        result = AsyncMock()
        char_id = kwargs.get("character_id")
        if char_id and char_id in faction_for:
            record = MagicMock()
            record.__getitem__ = MagicMock(side_effect=lambda k: faction_for[char_id] if k == "faction_id" else None)
            result.single = AsyncMock(return_value=record)
        else:
            result.single = AsyncMock(return_value=None)
        return result

    session.run = mock_run

    await break_pledge(
        session,
        pledger_id="char-1",
        pledgee_id="char-2",
        pledge_type="protect",
        tick=20,
    )

    # Faction swing queries should involve both faction pairs
    swing_calls = [
        kwargs for _, kwargs in calls_made
        if "src_faction_id" in kwargs and "delta" in kwargs
    ]
    assert len(swing_calls) == 2
    faction_pairs = {(c["src_faction_id"], c["dst_faction_id"]) for c in swing_calls}
    assert ("faction-a", "faction-b") in faction_pairs
    assert ("faction-b", "faction-a") in faction_pairs


@pytest.mark.asyncio
async def test_break_pledge_no_faction_swing_when_same_faction() -> None:
    session = AsyncMock()
    calls_made = []

    async def mock_run(query, **kwargs):
        calls_made.append((query, kwargs))
        result = AsyncMock()
        char_id = kwargs.get("character_id")
        if char_id:
            record = MagicMock()
            record.__getitem__ = MagicMock(side_effect=lambda k: "faction-a" if k == "faction_id" else None)
            result.single = AsyncMock(return_value=record)
        else:
            result.single = AsyncMock(return_value=None)
        return result

    session.run = mock_run

    await break_pledge(
        session,
        pledger_id="char-1",
        pledgee_id="char-2",
        pledge_type="protect",
        tick=20,
    )

    swing_calls = [
        kwargs for _, kwargs in calls_made
        if "src_faction_id" in kwargs
    ]
    assert len(swing_calls) == 0


# ---------------------------------------------------------------------------
# get_expiring_pledges_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_expiring_pledges_svc_delegates() -> None:
    expected = [{"pledger_id": "char-1", "pledge_type": "fealty"}]
    with patch(
        "npc_engine.graph.pledge_service.get_expiring_pledges",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_expiring_pledges_svc(session, tick_id=50)
        mock_fn.assert_called_once_with(session, tick_id=50)
        assert result == expected


# ---------------------------------------------------------------------------
# Context integration — assemble_tier_a_context includes active_pledges
# ---------------------------------------------------------------------------


def test_assemble_tier_a_context_includes_active_pledges() -> None:
    from npc_engine.retrieval.subgraph_retriever import assemble_tier_a_context
    import json

    pledges = [
        {"pledgee_id": "char-2", "pledgee_name": "Bob", "pledge_type": "protect", "severity": 80, "expires_at_tick": None, "is_active": True},
        {"pledgee_id": "char-3", "pledgee_name": "Carol", "pledge_type": "serve", "severity": 60, "expires_at_tick": 200, "is_active": True},
    ]
    items = assemble_tier_a_context(
        npc_id="npc-1",
        character_bundle={"character": {"id": "npc-1"}, "relations": []},
        events=[],
        location_id=None,
        location_context=None,
        active_pledges=pledges,
    )
    pledge_item = next((i for i in items if i.key == "active_pledges"), None)
    assert pledge_item is not None
    assert pledge_item.priority == 79
    data = json.loads(pledge_item.text)
    assert len(data) == 2
    assert data[0]["pledge_type"] == "protect"


def test_assemble_tier_a_context_skips_inactive_pledges() -> None:
    from npc_engine.retrieval.subgraph_retriever import assemble_tier_a_context

    pledges = [
        {"pledgee_id": "char-2", "pledge_type": "protect", "severity": 80, "is_active": False},
    ]
    items = assemble_tier_a_context(
        npc_id="npc-1",
        character_bundle={"character": {"id": "npc-1"}, "relations": []},
        events=[],
        location_id=None,
        location_context=None,
        active_pledges=pledges,
    )
    keys = [i.key for i in items]
    assert "active_pledges" not in keys


def test_assemble_tier_a_context_no_pledges_skips_item() -> None:
    from npc_engine.retrieval.subgraph_retriever import assemble_tier_a_context

    items = assemble_tier_a_context(
        npc_id="npc-1",
        character_bundle={"character": {"id": "npc-1"}, "relations": []},
        events=[],
        location_id=None,
        location_context=None,
        active_pledges=[],
    )
    keys = [i.key for i in items]
    assert "active_pledges" not in keys
