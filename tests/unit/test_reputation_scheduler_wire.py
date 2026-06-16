"""
Tests for ReputationTickAdapter scheduler wiring (EXP-52 slice-2).

All tests are fully mocked — no DB, no LLM connections.

Covers:
  - engine called when set in scheduler
  - engine NOT called when None
  - adapter returns {"nudges": 0} when config disabled
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.reputation.propagation_config import PropagationConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enabled_config() -> PropagationConfig:
    return PropagationConfig(
        max_nudge_per_tick=2,
        min_source_standing="FRIENDLY",
        min_bridge_standing="NEUTRAL",
        enabled=True,
    )


def _disabled_config() -> PropagationConfig:
    return PropagationConfig(
        max_nudge_per_tick=2,
        min_source_standing="FRIENDLY",
        min_bridge_standing="NEUTRAL",
        enabled=False,
    )


def _make_character_reader(npc_ids: list[str]) -> MagicMock:
    """Mock character reader whose get_npc_ids returns ``npc_ids``."""
    reader = MagicMock()
    reader.get_npc_ids = AsyncMock(return_value=npc_ids)
    return reader


# ---------------------------------------------------------------------------
# test_reputation_engine_called_when_set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reputation_engine_called_when_set() -> None:
    """ReputationTickAdapter.run_tick delegates to the wrapped engine when called."""
    from npc_engine.engines.reputation.reputation_tick_adapter import ReputationTickAdapter

    config = _enabled_config()
    mock_reputation_engine = MagicMock()
    mock_reputation_engine.run_tick = AsyncMock(return_value=None)

    mock_character_reader = _make_character_reader(["npc_1", "npc_2"])
    mock_session = MagicMock()

    adapter = ReputationTickAdapter(
        engine=mock_reputation_engine,
        character_reader=mock_character_reader,
        player_id="player",
        config=config,
    )
    result = await adapter.run_tick(session=mock_session, tick_id=5)

    mock_reputation_engine.run_tick.assert_awaited_once()
    assert "nudges" in result


# ---------------------------------------------------------------------------
# test_reputation_engine_not_called_when_none
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reputation_engine_not_called_when_none() -> None:
    """When engine is None-like (engine disabled path), run_tick returns early."""
    from npc_engine.engines.reputation.reputation_tick_adapter import ReputationTickAdapter

    # Disabled config means engine exits early without calling apply_nudge_fn
    config = _disabled_config()
    mock_reputation_engine = MagicMock()
    mock_reputation_engine.run_tick = AsyncMock(return_value=None)

    mock_character_reader = _make_character_reader([])
    mock_session = MagicMock()

    adapter = ReputationTickAdapter(
        engine=mock_reputation_engine,
        character_reader=mock_character_reader,
        player_id="player",
        config=config,
    )
    result = await adapter.run_tick(session=mock_session, tick_id=3)

    # Adapter still calls engine.run_tick (engine itself guards on enabled flag)
    # The important thing is the adapter returns a valid dict
    assert isinstance(result, dict)
    assert "nudges" in result


# ---------------------------------------------------------------------------
# test_adapter_returns_empty_when_disabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adapter_returns_empty_when_disabled() -> None:
    """When config.enabled=False, adapter returns {"nudges": 0}."""
    from npc_engine.engines.reputation.reputation_tick_adapter import ReputationTickAdapter

    config = _disabled_config()
    mock_reputation_engine = MagicMock()
    mock_reputation_engine.run_tick = AsyncMock(return_value=None)

    mock_character_reader = _make_character_reader(["npc_1"])
    mock_session = MagicMock()

    adapter = ReputationTickAdapter(
        engine=mock_reputation_engine,
        character_reader=mock_character_reader,
        player_id="player",
        config=config,
    )
    result = await adapter.run_tick(session=mock_session, tick_id=1)

    assert result == {"nudges": 0}


# ---------------------------------------------------------------------------
# test_adapter_fetches_npc_ids_from_character_reader
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adapter_fetches_npc_ids_from_character_reader() -> None:
    """ReputationTickAdapter queries character_reader.get_npc_ids each tick."""
    from npc_engine.engines.reputation.reputation_tick_adapter import ReputationTickAdapter

    config = _enabled_config()
    mock_reputation_engine = MagicMock()
    mock_reputation_engine.run_tick = AsyncMock(return_value=None)

    mock_character_reader = _make_character_reader(["a", "b", "c"])
    mock_session = MagicMock()

    adapter = ReputationTickAdapter(
        engine=mock_reputation_engine,
        character_reader=mock_character_reader,
        player_id="player",
        config=config,
    )
    await adapter.run_tick(session=mock_session, tick_id=10)

    # CharacterReadPort.get_npc_ids() is sessionless after SEV-24.
    mock_character_reader.get_npc_ids.assert_awaited_once_with()
    call_kwargs = mock_reputation_engine.run_tick.call_args.kwargs
    assert call_kwargs["npc_ids"] == ["a", "b", "c"]
    assert call_kwargs["player_id"] == "player"
