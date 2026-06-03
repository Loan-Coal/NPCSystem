"""Unit tests for gossip_spread_service.inject_rumor_belief."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.gossip_spread_service import inject_rumor_belief


class _FakeResult:
    async def consume(self) -> None:
        pass


@pytest.fixture
def session() -> AsyncMock:
    s = AsyncMock()
    s.run.return_value = _FakeResult()
    return s


@pytest.mark.asyncio
async def test_inject_returns_deterministic_event_id(session: AsyncMock) -> None:
    event_id = await inject_rumor_belief(
        session,
        target_npc_id="mira_innkeeper",
        rumor_text="Bandits on the northern road",
        severity=60,
        tick_id=5,
    )
    assert event_id == "rumor_plant_mira_innkeeper_5"


@pytest.mark.asyncio
async def test_inject_calls_session_run_once(session: AsyncMock) -> None:
    await inject_rumor_belief(
        session,
        target_npc_id="captain_sorn",
        rumor_text="The merchant stole from the guild",
        severity=70,
        tick_id=10,
    )
    session.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_inject_passes_correct_params(session: AsyncMock) -> None:
    await inject_rumor_belief(
        session,
        target_npc_id="old_henryk",
        rumor_text="Gold hidden in the tavern cellar",
        severity=40,
        tick_id=3,
    )
    _, kwargs = session.run.call_args
    assert kwargs["event_id"] == "rumor_plant_old_henryk_3"
    assert kwargs["rumor_text"] == "Gold hidden in the tavern cellar"
    assert kwargs["severity"] == 40
    assert kwargs["tick_id"] == 3
    assert kwargs["npc_id"] == "old_henryk"
    assert kwargs["knowledge_state"] == "rumor"
    assert kwargs["source_character_id"] == "player"


@pytest.mark.asyncio
async def test_inject_marks_event_as_fabricated(session: AsyncMock) -> None:
    """CYPHER_INJECT_RUMOR must set is_fabricated=true and is_canonical=false on the Event."""
    from npc_engine.graph.gossip_spread_service import CYPHER_INJECT_RUMOR

    assert "is_fabricated = true" in CYPHER_INJECT_RUMOR
    assert "is_canonical = false" in CYPHER_INJECT_RUMOR


@pytest.mark.asyncio
async def test_inject_different_ticks_produce_different_ids(session: AsyncMock) -> None:
    id_a = await inject_rumor_belief(session, "mira_innkeeper", "text", 50, tick_id=1)
    id_b = await inject_rumor_belief(session, "mira_innkeeper", "text", 50, tick_id=2)
    assert id_a != id_b
