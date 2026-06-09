"""
test_memory_service.py - Unit tests for memory_service and MemoryEngine.

Does NOT: connect to Neo4j. All graph calls are mocked.

Dependencies injected: None.
"""

from __future__ import annotations

import json
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.memory.memory_engine import MemoryEngine
from npc_engine.world.time_utils import TimePoint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a MagicMock that behaves like an AsyncSession with a transaction."""
    session = MagicMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    session.begin_transaction = AsyncMock(return_value=tx)
    return session


def _make_game_time(**kwargs) -> TimePoint:
    defaults = dict(year=1, season="spring", day=5, time_of_day="afternoon")
    defaults.update(kwargs)
    return TimePoint(**defaults)


# ---------------------------------------------------------------------------
# create_memory — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_memory_returns_uuid_string():
    session = _make_session()

    with patch(
        "npc_engine.graph.memory_service.uuid.uuid4", return_value="test-uuid-1234"
    ):
        from npc_engine.graph.memory_service import create_memory

        memory_id = await create_memory(
            session,
            character_id="char_1",
            content="Witnessed the burning of the market.",
            vividness=80,
            emotional_charge=40,
            game_time=_make_game_time(),
        )

    assert memory_id == "test-uuid-1234"
    session.begin_transaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_memory_serialises_game_time_as_json():
    """game_time should be stored as a JSON string with year/season/day/time_of_day."""
    session = _make_session()
    captured_params: list[dict] = []

    async def _run_capture(cypher, **params):
        captured_params.append(params)
        return AsyncMock()

    session.begin_transaction.return_value.__aenter__.return_value.run = _run_capture

    from npc_engine.graph.memory_service import create_memory

    await create_memory(
        session,
        character_id="char_1",
        content="something happened",
        vividness=70,
        emotional_charge=20,
        game_time=_make_game_time(year=3, season="autumn", day=14, time_of_day="night"),
    )

    assert len(captured_params) == 1
    payload = captured_params[0]
    game_time_data = json.loads(payload["created_at_game_time"])
    assert game_time_data["year"] == 3
    assert game_time_data["season"] == "autumn"
    assert game_time_data["day"] == 14
    assert game_time_data["time_of_day"] == "night"


# ---------------------------------------------------------------------------
# get_memories_for_character_svc — returns sorted list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_memories_returns_list_from_query():
    expected = [
        {"id": "m1", "content": "attack", "vividness": 80, "emotional_charge": 30},
        {"id": "m2", "content": "peace", "vividness": 40, "emotional_charge": 10},
    ]

    with patch(
        "npc_engine.graph.memory_service.get_memories_for_character",
        new_callable=AsyncMock,
        return_value=expected,
    ):
        from npc_engine.graph.memory_service import get_memories_for_character_svc

        rows = await get_memories_for_character_svc(
            MagicMock(), character_id="char_1", k=5
        )

    assert len(rows) == 2
    assert rows[0]["id"] == "m1"
    assert rows[0]["vividness"] == 80


# ---------------------------------------------------------------------------
# decay_all_vividness — clamps to 0
# decay_all_vividness uses session.begin_transaction() like create_memory.
# ---------------------------------------------------------------------------


def _make_decay_session(affected: int | None) -> MagicMock:
    """Return a session mock wired for decay_all_vividness (uses begin_transaction)."""
    session = MagicMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    record = MagicMock() if affected is not None else None
    if record is not None:
        record.__getitem__ = MagicMock(side_effect=lambda k: affected if k == "affected" else None)
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value=record)
    tx.run = AsyncMock(return_value=mock_result)
    session.begin_transaction = AsyncMock(return_value=tx)
    return session


@pytest.mark.asyncio
async def test_decay_all_vividness_returns_affected_count():
    session = _make_decay_session(affected=3)

    from npc_engine.graph.memory_service import decay_all_vividness

    count = await decay_all_vividness(session, decay_per_day=5)
    assert count == 3


@pytest.mark.asyncio
async def test_decay_all_vividness_returns_zero_when_no_memories():
    session = _make_decay_session(affected=None)

    from npc_engine.graph.memory_service import decay_all_vividness

    count = await decay_all_vividness(session)
    assert count == 0


# ---------------------------------------------------------------------------
# MemoryEngine.create_from_arousal — threshold logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_engine_creates_memory_when_arousal_above_70():
    engine = MemoryEngine()
    session = _make_session()

    with patch(
        "npc_engine.engines.memory.memory_engine.create_memory",
        new_callable=AsyncMock,
        return_value="new-mem-id",
    ) as mock_create:
        result = await engine.create_from_arousal(
            session,
            character_id="char_1",
            arousal=85,
            content="A dramatic scene.",
            game_time=_make_game_time(),
        )

    assert result == "new-mem-id"
    mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_memory_engine_skips_when_arousal_at_or_below_70():
    engine = MemoryEngine()
    session = _make_session()

    with patch(
        "npc_engine.engines.memory.memory_engine.create_memory",
        new_callable=AsyncMock,
    ) as mock_create:
        result_at = await engine.create_from_arousal(
            session,
            character_id="char_1",
            arousal=70,
            content="Mild discomfort.",
            game_time=_make_game_time(),
        )
        result_below = await engine.create_from_arousal(
            session,
            character_id="char_1",
            arousal=40,
            content="Indifferent.",
            game_time=_make_game_time(),
        )

    assert result_at is None
    assert result_below is None
    mock_create.assert_not_awaited()


# ---------------------------------------------------------------------------
# MemoryEngine.create_from_arousal — exact threshold boundary (arousal=71 vs 70)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_engine_creates_memory_at_arousal_71():
    """arousal=71 is strictly above the threshold (>70) and must create a memory."""
    engine = MemoryEngine()
    session = _make_session()

    with patch(
        "npc_engine.engines.memory.memory_engine.create_memory",
        new_callable=AsyncMock,
        return_value="threshold-mem-id",
    ) as mock_create:
        result = await engine.create_from_arousal(
            session,
            character_id="char_threshold",
            arousal=71,
            content="Threshold moment.",
            game_time=_make_game_time(),
        )

    assert result == "threshold-mem-id"
    mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_memory_engine_does_not_create_at_arousal_70():
    """arousal=70 is at the threshold (not strictly above) — must NOT create a memory."""
    engine = MemoryEngine()
    session = _make_session()

    with patch(
        "npc_engine.engines.memory.memory_engine.create_memory",
        new_callable=AsyncMock,
    ) as mock_create:
        result = await engine.create_from_arousal(
            session,
            character_id="char_threshold",
            arousal=70,
            content="Just below threshold.",
            game_time=_make_game_time(),
        )

    assert result is None
    mock_create.assert_not_awaited()


@pytest.mark.asyncio
async def test_memory_engine_emotional_charge_formula_at_threshold():
    """At arousal=71, emotional_charge should be min(100, 71-50) = 21."""
    engine = MemoryEngine()
    session = _make_session()
    captured: list[dict] = []

    async def _capture(sess, *, character_id, content, vividness, emotional_charge, game_time):
        captured.append({"emotional_charge": emotional_charge})
        return "ec-check-id"

    with patch("npc_engine.engines.memory.memory_engine.create_memory", side_effect=_capture):
        await engine.create_from_arousal(
            session,
            character_id="char_1",
            arousal=71,
            content="Minimal arousal.",
            game_time=_make_game_time(),
        )

    assert captured[0]["emotional_charge"] == 21


# ---------------------------------------------------------------------------
# get_memories_for_character_svc — empty result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_memories_svc_returns_empty_list_when_none():
    with patch(
        "npc_engine.graph.memory_service.get_memories_for_character",
        new_callable=AsyncMock,
        return_value=[],
    ):
        from npc_engine.graph.memory_service import get_memories_for_character_svc

        rows = await get_memories_for_character_svc(MagicMock(), character_id="no_char", k=5)

    assert rows == []


@pytest.mark.asyncio
async def test_get_memories_svc_passes_k_to_query():
    """k is forwarded to the underlying query function."""
    with patch(
        "npc_engine.graph.memory_service.get_memories_for_character",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_get:
        from npc_engine.graph.memory_service import get_memories_for_character_svc

        await get_memories_for_character_svc(MagicMock(), character_id="char_1", k=0)

    mock_get.assert_awaited_once_with(ANY, character_id="char_1", k=0)


@pytest.mark.asyncio
async def test_memory_engine_clamps_emotional_charge_to_100():
    engine = MemoryEngine()
    session = _make_session()
    captured_kwargs: list[dict] = []

    async def _capture_create(sess, *, character_id, content, vividness, emotional_charge, game_time):
        captured_kwargs.append({"emotional_charge": emotional_charge})
        return "some-id"

    with patch(
        "npc_engine.engines.memory.memory_engine.create_memory",
        side_effect=_capture_create,
    ):
        await engine.create_from_arousal(
            session,
            character_id="char_1",
            arousal=100,
            content="Peak moment.",
            game_time=_make_game_time(),
        )

    assert captured_kwargs[0]["emotional_charge"] <= 100
