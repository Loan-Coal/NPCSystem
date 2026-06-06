"""
test_memory_engine_weighted_decay.py — Unit tests for MemoryEngine.decay_vividness_weighted.

Does NOT: connect to Neo4j. All graph calls are mocked.
Dependencies injected: None.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.memory.memory_engine import MemoryEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a MagicMock that behaves like an AsyncSession."""
    return MagicMock()


# ---------------------------------------------------------------------------
# decay_vividness_weighted tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weighted_decay_calls_weighted_service():
    """decay_vividness_weighted calls decay_all_vividness_weighted, not the flat variant."""
    session = _make_session()
    engine = MemoryEngine()

    with patch(
        "npc_engine.engines.memory.memory_engine.decay_all_vividness_weighted",
        new_callable=AsyncMock,
        return_value=3,
    ) as mock_weighted, patch(
        "npc_engine.engines.memory.memory_engine.decay_all_vividness",
        new_callable=AsyncMock,
        return_value=99,
    ) as mock_flat:
        await engine.decay_vividness_weighted(session)

    mock_weighted.assert_called_once()
    mock_flat.assert_not_called()


@pytest.mark.asyncio
async def test_weighted_decay_uses_correct_defaults():
    """decay_vividness_weighted passes base_decay=5 and charge_divisor=20."""
    session = _make_session()
    engine = MemoryEngine()

    with patch(
        "npc_engine.engines.memory.memory_engine.decay_all_vividness_weighted",
        new_callable=AsyncMock,
        return_value=0,
    ) as mock_weighted:
        await engine.decay_vividness_weighted(session)

    mock_weighted.assert_called_once_with(
        session, base_decay=5, charge_divisor=20
    )


@pytest.mark.asyncio
async def test_weighted_decay_returns_count():
    """decay_vividness_weighted returns the int value from the service layer."""
    session = _make_session()
    engine = MemoryEngine()

    with patch(
        "npc_engine.engines.memory.memory_engine.decay_all_vividness_weighted",
        new_callable=AsyncMock,
        return_value=42,
    ):
        result = await engine.decay_vividness_weighted(session)

    assert result == 42


@pytest.mark.asyncio
async def test_flat_decay_unchanged():
    """decay_vividness (old path) still calls decay_all_vividness, not the weighted variant."""
    session = _make_session()
    engine = MemoryEngine()

    with patch(
        "npc_engine.engines.memory.memory_engine.decay_all_vividness",
        new_callable=AsyncMock,
        return_value=7,
    ) as mock_flat, patch(
        "npc_engine.engines.memory.memory_engine.decay_all_vividness_weighted",
        new_callable=AsyncMock,
        return_value=99,
    ) as mock_weighted:
        result = await engine.decay_vividness(session)

    mock_flat.assert_called_once()
    mock_weighted.assert_not_called()
    assert result == 7
