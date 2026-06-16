"""
test_memory_decay_tick.py - Unit tests for the MemoryDecayTick scheduler adapter (F1.7).

Verifies the forgetting-decay tick self-gates on its interval and delegates to
MemoryEngine.decay_vividness_weighted, returning the count of decayed memories. The
scheduler's session= kwarg is swallowed by run_tick (DEC-122 / SEV-24).

Dependencies injected: a fake MemoryEngine recording decay calls.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.engines.memory.memory_decay_tick import MemoryDecayTick


class _FakeMemoryEngine:
    def __init__(self, count: int) -> None:
        self._count = count
        self.calls = 0

    async def decay_vividness_weighted(self) -> int:
        self.calls += 1
        return self._count


@pytest.mark.asyncio
async def test_decays_on_interval_tick() -> None:
    """On a tick divisible by the interval, the weighted decay runs and returns its count."""
    engine = _FakeMemoryEngine(count=3)
    adapter = MemoryDecayTick(memory_engine=engine, interval=5)

    result = await adapter.run_tick(session=object(), tick_id=10)

    assert result == {"memories_decayed": 3}
    assert engine.calls == 1


@pytest.mark.asyncio
async def test_skips_off_interval_tick() -> None:
    """On a tick not divisible by the interval, no decay runs."""
    engine = _FakeMemoryEngine(count=3)
    adapter = MemoryDecayTick(memory_engine=engine, interval=5)

    result = await adapter.run_tick(session=object(), tick_id=7)

    assert result == {"memories_decayed": 0}
    assert engine.calls == 0


@pytest.mark.asyncio
async def test_interval_clamped_to_minimum_one() -> None:
    """A non-positive interval is clamped to 1 so decay runs every tick."""
    engine = _FakeMemoryEngine(count=1)
    adapter = MemoryDecayTick(memory_engine=engine, interval=0)

    result = await adapter.run_tick(session=object(), tick_id=3)

    assert result == {"memories_decayed": 1}
    assert engine.calls == 1
