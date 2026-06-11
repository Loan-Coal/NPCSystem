"""
Module: test_scheming_engine
Layer: tests/unit
Purpose: Unit tests for engines/scheming/scheming_engine.py — forms a capped
         scheme and advances one step. All graph I/O is mocked.
Dependencies: pytest, unittest.mock, npc_engine.engines.scheming.scheming_engine
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.config import Settings
from npc_engine.engines.scheming.scheming_engine import (
    SchemeInput,
    SchemeStepInput,
    SchemingEngine,
)
from npc_engine.graph.scheme_writer import SchemeRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_settings(max_active: int = 2) -> Settings:
    return Settings(MAX_ACTIVE_SCHEMES_PER_NPC=max_active)


def _make_engine(max_active: int = 2) -> SchemingEngine:
    return SchemingEngine(settings=_make_settings(max_active))


def _make_session() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# test_form_scheme_persists_node_and_edge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_form_scheme_persists_node_and_edge() -> None:
    """form_scheme calls upsert_scheme when NPC is below the cap."""
    engine = _make_engine(max_active=2)
    session = _make_session()

    with (
        patch(
            "npc_engine.engines.scheming.scheming_engine.get_active_schemes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.scheming.scheming_engine.upsert_scheme",
            new=AsyncMock(),
        ) as mock_upsert,
    ):
        result = await engine.form_scheme(
            session=session,
            inputs=SchemeInput(
                npc_id="aldric",
                goal="corner_grain_market",
                tick=1,
            ),
        )

    mock_upsert.assert_called_once()
    assert result is not None
    assert result.npc_id == "aldric"
    assert result.goal == "corner_grain_market"


# ---------------------------------------------------------------------------
# test_cap_blocks_excess_schemes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cap_blocks_excess_schemes() -> None:
    """form_scheme returns None (capped) when NPC already has MAX active schemes."""
    engine = _make_engine(max_active=2)
    session = _make_session()

    existing = [
        SchemeRecord(
            id=f"s{i}",
            npc_id="aldric",
            goal=f"goal_{i}",
            status="active",
            created_at_game_time="tick_1",
        )
        for i in range(2)
    ]

    with (
        patch(
            "npc_engine.engines.scheming.scheming_engine.get_active_schemes",
            new=AsyncMock(return_value=existing),
        ),
        patch(
            "npc_engine.engines.scheming.scheming_engine.upsert_scheme",
            new=AsyncMock(),
        ) as mock_upsert,
    ):
        result = await engine.form_scheme(
            session=session,
            inputs=SchemeInput(
                npc_id="aldric",
                goal="third_scheme",
                tick=5,
            ),
        )

    mock_upsert.assert_not_called()
    assert result is None


# ---------------------------------------------------------------------------
# test_advance_step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_advance_step_calls_add_scheme_step() -> None:
    """advance_step calls add_scheme_step with the correct params."""
    engine = _make_engine()
    session = _make_session()

    with patch(
        "npc_engine.engines.scheming.scheming_engine.add_scheme_step",
        new=AsyncMock(),
    ) as mock_add:
        await engine.advance_step(
            session=session,
            inputs=SchemeStepInput(
                scheme_id="s1",
                event_id="evt_42",
                step_order=1,
                completed=False,
            ),
        )

    mock_add.assert_called_once()
    _, kwargs = mock_add.call_args
    assert kwargs["scheme_id"] == "s1"
    assert kwargs["event_id"] == "evt_42"
    assert kwargs["step_order"] == 1
    assert kwargs["completed"] is False


@pytest.mark.asyncio
async def test_advance_step_marks_completed() -> None:
    """advance_step correctly forwards completed=True."""
    engine = _make_engine()
    session = _make_session()

    with patch(
        "npc_engine.engines.scheming.scheming_engine.add_scheme_step",
        new=AsyncMock(),
    ) as mock_add:
        await engine.advance_step(
            session=session,
            inputs=SchemeStepInput(
                scheme_id="s2",
                event_id="evt_99",
                step_order=3,
                completed=True,
            ),
        )

    params = {**mock_add.call_args[1]}
    assert params["completed"] is True
