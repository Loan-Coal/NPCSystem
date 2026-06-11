"""
test_memory_engine.py - Unit tests for MemoryEngine.

Covers:
- create_from_arousal: high-arousal path (memory created) and below-threshold skip.
- create_from_semantic_triggers: keyword-hit path (memory created) and mundane skip.

Does NOT: connect to Neo4j. All graph calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.memory.memory_engine import MemoryEngine
from npc_engine.world.time_utils import TimePoint

_MODULE = "npc_engine.engines.memory.memory_engine"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_session() -> MagicMock:
    """Return a MagicMock that behaves like an AsyncSession."""
    session = MagicMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    session.begin_transaction = AsyncMock(return_value=tx)
    return session


def _make_game_time() -> TimePoint:
    return TimePoint(year=1, season="spring", day=1, time_of_day="morning")


# ---------------------------------------------------------------------------
# create_from_arousal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_from_arousal_high_arousal_creates_memory(mock_session):
    engine = MemoryEngine()
    with patch(f"{_MODULE}.create_memory", new_callable=AsyncMock, return_value="mem-arousal-001") as mock_cm:
        result = await engine.create_from_arousal(
            mock_session,
            character_id="npc_1",
            arousal=80,
            content="A fierce battle erupted in the square",
            game_time=_make_game_time(),
        )
    assert result == "mem-arousal-001"
    mock_cm.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_from_arousal_low_arousal_returns_none(mock_session):
    engine = MemoryEngine()
    with patch(f"{_MODULE}.create_memory", new_callable=AsyncMock) as mock_cm:
        result = await engine.create_from_arousal(
            mock_session,
            character_id="npc_1",
            arousal=40,
            content="Someone walked past the tavern",
            game_time=_make_game_time(),
        )
    assert result is None
    mock_cm.assert_not_awaited()


# ---------------------------------------------------------------------------
# create_from_semantic_triggers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_from_semantic_triggers_fires_on_keyword(mock_session):
    engine = MemoryEngine()
    with patch(f"{_MODULE}.create_memory", new_callable=AsyncMock, return_value="mem-001") as mock_cm:
        result = await engine.create_from_semantic_triggers(
            mock_session,
            character_id="npc_1",
            content="The king ordered an execution at dawn",
            emotional_charge=10,
            game_time=TimePoint(year=1, season="spring", day=1, time_of_day="morning"),
        )
    assert result == "mem-001"
    mock_cm.assert_called_once()


@pytest.mark.asyncio
async def test_create_from_semantic_triggers_skips_mundane(mock_session):
    engine = MemoryEngine()
    with patch(f"{_MODULE}.create_memory", new_callable=AsyncMock) as mock_cm:
        result = await engine.create_from_semantic_triggers(
            mock_session,
            character_id="npc_1",
            content="The merchant sold bread in the market",
            emotional_charge=5,
            game_time=TimePoint(year=1, season="spring", day=1, time_of_day="morning"),
        )
    assert result is None
    mock_cm.assert_not_called()


@pytest.mark.asyncio
async def test_create_from_semantic_triggers_case_insensitive(mock_session):
    """Keyword match must be case-insensitive."""
    engine = MemoryEngine()
    with patch(f"{_MODULE}.create_memory", new_callable=AsyncMock, return_value="mem-002") as mock_cm:
        result = await engine.create_from_semantic_triggers(
            mock_session,
            character_id="npc_2",
            content="Reports of BETRAYAL spread across the city",
            emotional_charge=20,
            game_time=_make_game_time(),
        )
    assert result == "mem-002"
    mock_cm.assert_called_once()


@pytest.mark.asyncio
async def test_create_from_semantic_triggers_uses_semantic_vividness(mock_session):
    """Memory must be formed with _SEMANTIC_VIVIDNESS (60), not the arousal vividness (80)."""
    engine = MemoryEngine()
    with patch(f"{_MODULE}.create_memory", new_callable=AsyncMock, return_value="mem-003") as mock_cm:
        await engine.create_from_semantic_triggers(
            mock_session,
            character_id="npc_3",
            content="A plague swept through the northern villages",
            emotional_charge=15,
            game_time=_make_game_time(),
        )
    call_kwargs = mock_cm.call_args.kwargs
    assert call_kwargs["vividness"] == 60


@pytest.mark.asyncio
async def test_create_from_semantic_triggers_forwards_emotional_charge(mock_session):
    """The emotional_charge passed in must reach create_memory unchanged."""
    engine = MemoryEngine()
    with patch(f"{_MODULE}.create_memory", new_callable=AsyncMock, return_value="mem-004") as mock_cm:
        await engine.create_from_semantic_triggers(
            mock_session,
            character_id="npc_4",
            content="The coup toppled the old regime at midnight",
            emotional_charge=42,
            game_time=_make_game_time(),
        )
    call_kwargs = mock_cm.call_args.kwargs
    assert call_kwargs["emotional_charge"] == 42


# ---------------------------------------------------------------------------
# EXP-211: subject_player_id population
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_tagged_with_subject_player_id(mock_session):
    """When a player_id is supplied to create_from_arousal, it must be forwarded to
    create_memory as subject_player_id so the memory is player-scoped."""
    engine = MemoryEngine()
    with patch(f"{_MODULE}.create_memory", new_callable=AsyncMock, return_value="mem-p001") as mock_cm:
        result = await engine.create_from_arousal(
            mock_session,
            character_id="npc_1",
            arousal=85,
            content="The player revealed a shocking secret",
            game_time=_make_game_time(),
            player_id="player_hero",
        )
    assert result == "mem-p001"
    call_kwargs = mock_cm.call_args.kwargs
    assert call_kwargs.get("subject_player_id") == "player_hero", (
        "subject_player_id must be forwarded to create_memory when player_id is given"
    )


@pytest.mark.asyncio
async def test_memory_without_player_id_has_no_subject_player_id(mock_session):
    """When player_id is not supplied, subject_player_id must be absent (None) in create_memory."""
    engine = MemoryEngine()
    with patch(f"{_MODULE}.create_memory", new_callable=AsyncMock, return_value="mem-p002") as mock_cm:
        await engine.create_from_arousal(
            mock_session,
            character_id="npc_2",
            arousal=90,
            content="The dragon attacked the village",
            game_time=_make_game_time(),
        )
    call_kwargs = mock_cm.call_args.kwargs
    assert call_kwargs.get("subject_player_id") is None, (
        "subject_player_id must be None when no player_id is given"
    )


# ---------------------------------------------------------------------------
# EXP-212: compute_salience
# ---------------------------------------------------------------------------


def test_compute_salience_forgettable_below_threshold():
    """A memory with low recall_count, low vividness, low charge is forgettable."""
    from npc_engine.engines.memory.memory_engine import compute_salience, is_forgettable
    from npc_engine.config import Settings

    settings = Settings(API_KEY_SECRET="npc_dev_secret_2026_alpha")  # type: ignore[call-arg]
    salience = compute_salience(vividness=5, emotional_charge=5, recall_count=0)
    assert salience < settings.MEMORY_FORGET_THRESHOLD, (
        "Memory with low vividness/charge/recall should be below forget threshold"
    )
    assert is_forgettable(
        salience=salience,
        never_forget=False,
        threshold=settings.MEMORY_FORGET_THRESHOLD,
    ), "Low-salience memory with never_forget=False should be forgettable"


def test_never_forget_memory_not_forgettable():
    """A memory with never_forget=True must never be forgettable, regardless of salience."""
    from npc_engine.engines.memory.memory_engine import compute_salience, is_forgettable
    from npc_engine.config import Settings

    settings = Settings(API_KEY_SECRET="npc_dev_secret_2026_alpha")  # type: ignore[call-arg]
    salience = compute_salience(vividness=0, emotional_charge=0, recall_count=0)
    assert not is_forgettable(
        salience=salience,
        never_forget=True,
        threshold=settings.MEMORY_FORGET_THRESHOLD,
    ), "A never_forget memory must never be marked forgettable"


def test_high_salience_memory_not_forgettable():
    """A memory with high vividness and charge must exceed the threshold."""
    from npc_engine.engines.memory.memory_engine import compute_salience, is_forgettable
    from npc_engine.config import Settings

    settings = Settings(API_KEY_SECRET="npc_dev_secret_2026_alpha")  # type: ignore[call-arg]
    salience = compute_salience(vividness=90, emotional_charge=80, recall_count=10)
    assert salience >= settings.MEMORY_FORGET_THRESHOLD, (
        "High vividness/charge/recall memory must exceed forget threshold"
    )
    assert not is_forgettable(
        salience=salience,
        never_forget=False,
        threshold=settings.MEMORY_FORGET_THRESHOLD,
    )
