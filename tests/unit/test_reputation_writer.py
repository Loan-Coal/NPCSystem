"""
test_reputation_writer.py - Unit tests for reputation mutation functions.

Does NOT: execute graph I/O.

Dependencies injected: None (stub transaction).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from npc_engine.utils.errors import ReputationNotFoundError


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, record: dict | None) -> None:
        self._record = record

    async def single(self) -> dict | None:
        return self._record

    async def consume(self) -> None:
        pass


class _FakeTx:
    def __init__(self, single_record: dict | None = None) -> None:
        self._record = single_record
        self.last_query: str = ""
        self.last_params: dict[str, Any] = {}

    async def run(self, query: str, **params: Any) -> _FakeResult:
        self.last_query = query
        self.last_params = params
        return _FakeResult(self._record)


# ---------------------------------------------------------------------------
# Tests: set_reputation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_reputation_succeeds_with_valid_standing() -> None:
    from npc_engine.graph.reputation.reputation_writer import set_reputation

    tx = _FakeTx(single_record={"standing": 40})
    await set_reputation(tx, character_id="char_1", faction_id="fac_1", standing=40)
    assert tx.last_params["standing"] == 40


@pytest.mark.asyncio
async def test_set_reputation_clamps_above_100() -> None:
    from npc_engine.graph.reputation.reputation_writer import set_reputation

    tx = _FakeTx(single_record={"standing": 100})
    await set_reputation(tx, character_id="char_1", faction_id="fac_1", standing=150)
    assert tx.last_params["standing"] == 100


@pytest.mark.asyncio
async def test_set_reputation_clamps_below_minus_100() -> None:
    from npc_engine.graph.reputation.reputation_writer import set_reputation

    tx = _FakeTx(single_record={"standing": -100})
    await set_reputation(tx, character_id="char_1", faction_id="fac_1", standing=-150)
    assert tx.last_params["standing"] == -100


@pytest.mark.asyncio
async def test_set_reputation_raises_when_node_missing() -> None:
    from npc_engine.graph.reputation.reputation_writer import set_reputation

    tx = _FakeTx(single_record=None)
    with pytest.raises(ReputationNotFoundError):
        await set_reputation(tx, character_id="char_1", faction_id="fac_missing", standing=50)


# ---------------------------------------------------------------------------
# Tests: adjust_reputation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adjust_reputation_increases_standing() -> None:
    from npc_engine.graph.reputation.reputation_writer import adjust_reputation

    # First run (read) returns 30, second run (write) returns 50
    call_count = 0

    class _CountingTx:
        async def run(self, query: str, **params: Any) -> _FakeResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeResult({"standing": 30})
            return _FakeResult({"standing": 50})

    result = await adjust_reputation(_CountingTx(), character_id="char_1", faction_id="fac_1", delta=20)
    assert result == 50


@pytest.mark.asyncio
async def test_adjust_reputation_clamps_at_ceiling() -> None:
    from npc_engine.graph.reputation.reputation_writer import adjust_reputation

    call_count = 0

    class _CeilingTx:
        async def run(self, query: str, **params: Any) -> _FakeResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeResult({"standing": 90})
            return _FakeResult({"standing": params.get("standing", 100)})

    result = await adjust_reputation(_CeilingTx(), character_id="char_1", faction_id="fac_1", delta=50)
    assert result == 100


@pytest.mark.asyncio
async def test_adjust_reputation_clamps_at_floor() -> None:
    from npc_engine.graph.reputation.reputation_writer import adjust_reputation

    call_count = 0

    class _FloorTx:
        async def run(self, query: str, **params: Any) -> _FakeResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeResult({"standing": -80})
            return _FakeResult({"standing": params.get("standing", -100)})

    result = await adjust_reputation(_FloorTx(), character_id="char_1", faction_id="fac_1", delta=-50)
    assert result == -100


@pytest.mark.asyncio
async def test_adjust_reputation_defaults_to_zero_when_no_existing_edge() -> None:
    from npc_engine.graph.reputation.reputation_writer import adjust_reputation

    call_count = 0

    class _NoEdgeTx:
        async def run(self, query: str, **params: Any) -> _FakeResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeResult(None)
            return _FakeResult({"standing": params.get("standing", 30)})

    result = await adjust_reputation(_NoEdgeTx(), character_id="char_1", faction_id="fac_1", delta=30)
    assert result == 30
