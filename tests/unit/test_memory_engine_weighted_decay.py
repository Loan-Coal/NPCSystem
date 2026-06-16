"""
test_memory_engine_weighted_decay.py — Unit tests for MemoryEngine.decay_vividness_weighted.

Does NOT: connect to Neo4j. The MemoryGraphPort is replaced with a recording fake.
Dependencies injected: a fake MemoryGraphPort.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.engines.memory.memory_engine import MemoryEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeMemoryRepo:
    """Records which decay method the engine calls and with what kwargs."""

    def __init__(self, *, flat: int = 0, weighted: int = 0) -> None:
        self._flat = flat
        self._weighted = weighted
        self.flat_calls = 0
        self.weighted_calls: list[dict[str, Any]] = []

    async def create_memory(self, **_: Any) -> str:
        return "mem"

    async def decay_all_vividness(self) -> int:
        self.flat_calls += 1
        return self._flat

    async def decay_all_vividness_weighted(self, *, base_decay: int, charge_divisor: int) -> int:
        self.weighted_calls.append({"base_decay": base_decay, "charge_divisor": charge_divisor})
        return self._weighted


# ---------------------------------------------------------------------------
# decay_vividness_weighted tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weighted_decay_calls_weighted_service():
    """decay_vividness_weighted calls decay_all_vividness_weighted, not the flat variant."""
    repo = _FakeMemoryRepo(flat=99, weighted=3)
    engine = MemoryEngine(memory_repo=repo)

    await engine.decay_vividness_weighted()

    assert len(repo.weighted_calls) == 1
    assert repo.flat_calls == 0


@pytest.mark.asyncio
async def test_weighted_decay_uses_correct_defaults():
    """decay_vividness_weighted passes base_decay=5 and charge_divisor=20."""
    repo = _FakeMemoryRepo(weighted=0)
    engine = MemoryEngine(memory_repo=repo)

    await engine.decay_vividness_weighted()

    assert repo.weighted_calls == [{"base_decay": 5, "charge_divisor": 20}]


@pytest.mark.asyncio
async def test_weighted_decay_returns_count():
    """decay_vividness_weighted returns the int value from the port."""
    repo = _FakeMemoryRepo(weighted=42)
    engine = MemoryEngine(memory_repo=repo)

    result = await engine.decay_vividness_weighted()

    assert result == 42


@pytest.mark.asyncio
async def test_flat_decay_unchanged():
    """decay_vividness (old path) still calls decay_all_vividness, not the weighted variant."""
    repo = _FakeMemoryRepo(flat=7, weighted=99)
    engine = MemoryEngine(memory_repo=repo)

    result = await engine.decay_vividness()

    assert repo.flat_calls == 1
    assert repo.weighted_calls == []
    assert result == 7
