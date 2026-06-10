"""
Unit tests for EmotionUpdater write-through, label inertia, and EmotionBootstrapper.

Covers:
- apply_dialogue_mood calls EmotionGraphWriter when injected (test 3)
- apply_dialogue_mood does not crash when no writer injected (test 4)
- VadEmotionModel label inertia below _MIN_AROUSAL_TO_SHIFT_LABEL (test 5)
- EmotionBootstrapper.load_from_graph seeds the store from graph data (test 6)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.emotion.emotion_bootstrap import EmotionBootstrapper
from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.emotion.emotion_updater import EmotionUpdater
from npc_engine.engines.emotion.vad_emotion_model import (
    VadEmotionModel,
    _MIN_AROUSAL_TO_SHIFT_LABEL,
)
from npc_engine.graph.emotion_writer import EmotionGraphWriter


@pytest.mark.asyncio
async def test_apply_dialogue_mood_writes_through() -> None:
    """apply_dialogue_mood must call writer.write_emotion when a writer is injected."""
    store = EmotionStore()
    mock_writer = MagicMock(spec=EmotionGraphWriter)
    mock_writer.write_emotion = AsyncMock()
    mock_session = MagicMock()

    updater = EmotionUpdater(emotion_store=store, writer=mock_writer)

    await updater.apply_dialogue_mood(
        npc_id="npc-1",
        mood_update="warm",
        session=mock_session,
        tick=5,
    )

    mock_writer.write_emotion.assert_called_once()
    call_kwargs = mock_writer.write_emotion.call_args[1]
    assert call_kwargs["npc_id"] == "npc-1"
    assert call_kwargs["tick"] == 5
    assert isinstance(call_kwargs["state"], EmotionState)


@pytest.mark.asyncio
async def test_apply_dialogue_mood_no_writer_no_crash() -> None:
    """apply_dialogue_mood must not crash when no writer is injected (default None)."""
    store = EmotionStore()
    updater = EmotionUpdater(emotion_store=store)  # no writer

    # Should complete without AttributeError or any exception
    state = await updater.apply_dialogue_mood(npc_id="npc-1", mood_update="neutral")
    assert isinstance(state, EmotionState)


@pytest.mark.asyncio
async def test_label_not_replaced_below_arousal_threshold() -> None:
    """VadEmotionModel must keep previous label when new arousal < _MIN_AROUSAL_TO_SHIFT_LABEL."""
    model = VadEmotionModel()

    # Build a previous state with label "neutral" and arousal below threshold
    previous = EmotionState(valence=50, arousal=5, label="neutral")

    # apply_mood_hint would normally set label to "warm" but arousal after increment
    # stays below _MIN_AROUSAL_TO_SHIFT_LABEL (20), so label must be preserved.
    # Use arousal_increment=1 so resulting arousal = 5 + 1 = 6, still < 20.
    result = model.apply_mood_hint(previous, mood_label="warm", arousal_increment=1)

    assert result.arousal == 6
    assert result.label == "neutral", (
        f"Expected label='neutral' (preserved due to low arousal={result.arousal} "
        f"< threshold={_MIN_AROUSAL_TO_SHIFT_LABEL}), got '{result.label}'"
    )


@pytest.mark.asyncio
async def test_emotion_bootstrapper_populates_store() -> None:
    """EmotionBootstrapper.load_from_graph must seed the store from graph records."""
    bootstrapper = EmotionBootstrapper()
    store = EmotionStore()

    mock_session = MagicMock()

    # Simulate Neo4j result records as list of dicts
    record_npc1 = {
        "emotion_valence": 60,
        "emotion_arousal": 40,
        "emotion_mood_label": "warm",
        "emotion_updated_at_tick": 10,
    }
    record_npc2 = {
        "emotion_valence": None,
        "emotion_arousal": None,
        "emotion_mood_label": None,
        "emotion_updated_at_tick": None,
    }

    async def mock_run(query: str, **kwargs: object):  # noqa: ANN001
        npc_id = kwargs.get("npc_id")
        if npc_id == "npc-1":
            record = MagicMock()
            record.__getitem__ = lambda self, key: record_npc1[key]
            rows = [record]
        else:
            record = MagicMock()
            record.__getitem__ = lambda self, key: record_npc2[key]
            rows = [record]
        result = _AsyncResult(rows)
        return result

    mock_session.run = mock_run

    await bootstrapper.load_from_graph(
        session=mock_session,
        store=store,
        npc_ids=["npc-1", "npc-2"],
    )

    state_npc1 = await store.get("npc-1")
    assert state_npc1.valence == 60, f"expected valence=60, got {state_npc1.valence}"
    assert state_npc1.arousal == 40, f"expected arousal=40, got {state_npc1.arousal}"
    assert state_npc1.label == "warm", f"expected label='warm', got '{state_npc1.label}'"

    # npc-2 has no stored emotion — store should hold a neutral default
    state_npc2 = await store.get("npc-2")
    assert state_npc2.valence == 0, f"expected valence=0 (neutral), got {state_npc2.valence}"
    assert state_npc2.arousal == 0, f"expected arousal=0 (neutral), got {state_npc2.arousal}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AsyncResult:
    """Minimal async-iterable mock for Neo4j query results."""

    def __init__(self, items: list) -> None:
        self._items = items

    def __aiter__(self) -> _AsyncResult:
        self._iter = iter(self._items)
        return self

    async def __anext__(self):  # noqa: ANN201
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    async def consume(self) -> None:
        """No-op consume for test compatibility."""
