"""Unit tests for MoodContagionEngine — all Neo4j calls mocked."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.mood.mood_contagion_engine import MoodContagionEngine, _blend


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


@pytest.fixture
def emotion_store():
    store = EmotionStore()
    store.set("npc_a", EmotionState(valence=80, arousal=70, label="elated"))
    store.set("npc_b", EmotionState(valence=-60, arousal=20, label="melancholic"))
    return store


@pytest.fixture
def engine(emotion_store):
    return MoodContagionEngine(emotion_store=emotion_store, affection_threshold=50)


@pytest.mark.asyncio
async def test_mood_blends_correctly(engine, emotion_store):
    session = AsyncMock()
    with (
        patch(
            "npc_engine.engines.mood.mood_contagion_engine.get_co_located_affectionate_pairs",
            new=AsyncMock(return_value=[("npc_a", "npc_b")]),
        ),
        patch(
            "npc_engine.engines.mood.mood_contagion_engine.set_character_mood",
            new=AsyncMock(),
        ),
    ):
        await engine.run_tick(session=session, tick_id=1)

    state_a = emotion_store.get("npc_a")
    assert state_a.valence < 80, "happy NPC should drift toward sad partner"


@pytest.mark.asyncio
async def test_no_contagion_when_no_pairs(engine, emotion_store):
    session = AsyncMock()
    with (
        patch(
            "npc_engine.engines.mood.mood_contagion_engine.get_co_located_affectionate_pairs",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.mood.mood_contagion_engine.set_character_mood",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session=session, tick_id=1)

    assert result["affected"] == 0
    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_mood_persisted_to_neo4j(engine, emotion_store):
    session = AsyncMock()
    with (
        patch(
            "npc_engine.engines.mood.mood_contagion_engine.get_co_located_affectionate_pairs",
            new=AsyncMock(return_value=[("npc_a", "npc_b")]),
        ),
        patch(
            "npc_engine.engines.mood.mood_contagion_engine.set_character_mood",
            new=AsyncMock(),
        ) as mock_set,
    ):
        await engine.run_tick(session=session, tick_id=1)

    assert mock_set.call_count == 2, "should persist both NPCs"
    call_ids = {c.kwargs["character_id"] for c in mock_set.call_args_list}
    assert call_ids == {"npc_a", "npc_b"}


@pytest.mark.asyncio
async def test_run_tick_returns_affected_count(engine):
    session = AsyncMock()
    with (
        patch(
            "npc_engine.engines.mood.mood_contagion_engine.get_co_located_affectionate_pairs",
            new=AsyncMock(return_value=[("npc_a", "npc_b"), ("npc_c", "npc_d")]),
        ),
        patch(
            "npc_engine.engines.mood.mood_contagion_engine.set_character_mood",
            new=AsyncMock(),
        ),
    ):
        result = await engine.run_tick(session=session, tick_id=5)

    assert result["tick_id"] == 5
    assert result["affected"] == 2


# ---------------------------------------------------------------------------
# MoodContagionEngine.initialize
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_loads_moods_into_store():
    store = EmotionStore()
    engine = MoodContagionEngine(emotion_store=store)
    session = AsyncMock()

    stored_moods = [
        {"character_id": "npc_x", "mood": "warm", "intensity": 0.4},
        {"character_id": "npc_y", "mood": "melancholic", "intensity": 0.3},
    ]
    with patch(
        "npc_engine.engines.mood.mood_contagion_engine.get_all_character_moods",
        new=AsyncMock(return_value=stored_moods),
    ):
        count = await engine.initialize(session=session)

    assert count == 2
    assert store.get("npc_x").label == "warm"
    assert store.get("npc_y").label == "melancholic"


@pytest.mark.asyncio
async def test_initialize_empty_db_returns_zero():
    store = EmotionStore()
    engine = MoodContagionEngine(emotion_store=store)
    session = AsyncMock()

    with patch(
        "npc_engine.engines.mood.mood_contagion_engine.get_all_character_moods",
        new=AsyncMock(return_value=[]),
    ):
        count = await engine.initialize(session=session)

    assert count == 0
