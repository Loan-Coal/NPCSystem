"""Unit tests for MoodContagionEngine — graph access via a mocked MoodGraphPort."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.mood.mood_contagion_engine import MoodContagionEngine, _blend


def _make_repo(
    pairs: list[tuple[str, str]] | None = None,
    moods: list[dict[str, Any]] | None = None,
) -> AsyncMock:
    """Build a mock MoodGraphPort returning the given pairs/moods."""
    repo = AsyncMock()
    repo.get_co_located_affectionate_pairs = AsyncMock(return_value=pairs or [])
    repo.get_all_character_moods = AsyncMock(return_value=moods or [])
    repo.set_character_mood = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# _blend helper
# ---------------------------------------------------------------------------


def test_blend_moves_toward_other():
    happy = EmotionState(valence=80, arousal=60, label="warm")
    sad = EmotionState(valence=-60, arousal=20, label="melancholic")
    blended = _blend(happy, sad)
    assert blended.valence < happy.valence
    assert blended.arousal < happy.arousal


def test_blend_is_immutable():
    a = EmotionState(valence=50, arousal=40, label="warm")
    b = EmotionState(valence=-50, arousal=30, label="melancholic")
    result = _blend(a, b)
    assert result is not a
    assert result is not b


def test_blend_clamps_valence():
    extreme_pos = EmotionState(valence=100, arousal=100, label="elated")
    slightly_more = EmotionState(valence=100, arousal=100, label="elated")
    result = _blend(extreme_pos, slightly_more)
    assert result.valence <= 100


def test_blend_neutral_npc_unaffected_by_neutral():
    a = EmotionState(valence=0, arousal=20, label="neutral")
    b = EmotionState(valence=0, arousal=20, label="neutral")
    result = _blend(a, b)
    assert result.valence == 0
    assert result.arousal == 20


# ---------------------------------------------------------------------------
# MoodContagionEngine.run_tick
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def emotion_store():
    store = EmotionStore()
    await store.set("npc_a", EmotionState(valence=80, arousal=70, label="elated"))
    await store.set("npc_b", EmotionState(valence=-60, arousal=20, label="melancholic"))
    return store


@pytest.mark.asyncio
async def test_mood_blends_correctly(emotion_store):
    repo = _make_repo(pairs=[("npc_a", "npc_b")])
    engine = MoodContagionEngine(emotion_store=emotion_store, mood_repo=repo, affection_threshold=50)

    await engine.run_tick(tick_id=1)

    state_a = await emotion_store.get("npc_a")
    assert state_a.valence < 80, "happy NPC should drift toward sad partner"


@pytest.mark.asyncio
async def test_no_contagion_when_no_pairs(emotion_store):
    repo = _make_repo(pairs=[])
    engine = MoodContagionEngine(emotion_store=emotion_store, mood_repo=repo, affection_threshold=50)

    result = await engine.run_tick(tick_id=1)

    assert result["affected"] == 0
    repo.set_character_mood.assert_not_called()


@pytest.mark.asyncio
async def test_mood_persisted_to_neo4j(emotion_store):
    repo = _make_repo(pairs=[("npc_a", "npc_b")])
    engine = MoodContagionEngine(emotion_store=emotion_store, mood_repo=repo, affection_threshold=50)

    await engine.run_tick(tick_id=1)

    assert repo.set_character_mood.call_count == 2, "should persist both NPCs"
    call_ids = {c.kwargs["character_id"] for c in repo.set_character_mood.call_args_list}
    assert call_ids == {"npc_a", "npc_b"}


@pytest.mark.asyncio
async def test_scheduler_session_kwarg_is_ignored(emotion_store):
    """The scheduler still passes session=...; the engine accepts and ignores it."""
    repo = _make_repo(pairs=[("npc_a", "npc_b")])
    engine = MoodContagionEngine(emotion_store=emotion_store, mood_repo=repo, affection_threshold=50)

    result = await engine.run_tick(session=object(), tick_id=1)

    assert result["affected"] == 1


@pytest.mark.asyncio
async def test_run_tick_returns_affected_count(emotion_store):
    repo = _make_repo(pairs=[("npc_a", "npc_b"), ("npc_c", "npc_d")])
    engine = MoodContagionEngine(emotion_store=emotion_store, mood_repo=repo, affection_threshold=50)

    result = await engine.run_tick(tick_id=5)

    assert result["tick_id"] == 5
    assert result["affected"] == 2


# ---------------------------------------------------------------------------
# MoodContagionEngine.initialize
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_loads_moods_into_store():
    store = EmotionStore()
    stored_moods = [
        {"character_id": "npc_x", "mood": "warm", "intensity": 0.4},
        {"character_id": "npc_y", "mood": "melancholic", "intensity": 0.3},
    ]
    engine = MoodContagionEngine(emotion_store=store, mood_repo=_make_repo(moods=stored_moods))

    count = await engine.initialize()

    assert count == 2
    assert (await store.get("npc_x")).label == "warm"
    assert (await store.get("npc_y")).label == "melancholic"


@pytest.mark.asyncio
async def test_initialize_empty_db_returns_zero():
    store = EmotionStore()
    engine = MoodContagionEngine(emotion_store=store, mood_repo=_make_repo(moods=[]))

    count = await engine.initialize()

    assert count == 0
