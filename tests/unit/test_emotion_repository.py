"""Unit tests for Neo4jEmotionRepository (DEC-122 / SEV-24 Wave 2 emotion slice).

Covers the session-per-call write-through adapter against a fake GraphDB and the
session-free EmotionUpdater write-through via an injected EmotionGraphPort.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.emotion.emotion_updater import EmotionUpdater
from npc_engine.graph.repositories.emotion_repository import Neo4jEmotionRepository

_EMOTION_MOD = "npc_engine.graph.repositories.emotion_repository"


class _FakeGraphDB:
    def __init__(self, session: Any) -> None:
        self._session = session
        self.connect_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[Any]:
        yield self._session


@pytest.mark.asyncio
async def test_write_emotion_opens_session_and_delegates_to_writer() -> None:
    """Adapter must connect, open a session, and delegate to EmotionGraphWriter."""
    session = object()
    db = _FakeGraphDB(session)

    with patch(f"{_EMOTION_MOD}.EmotionGraphWriter") as mock_cls:
        instance = mock_cls.return_value
        instance.write_emotion = AsyncMock()
        repo = Neo4jEmotionRepository(db)  # type: ignore[arg-type]
        await repo.write_emotion(
            npc_id="npc-1", valence=10, arousal=20, label="warm", tick=7
        )

    assert db.connect_calls == 1
    instance.write_emotion.assert_awaited_once_with(
        session=session, npc_id="npc-1", valence=10, arousal=20, label="warm", tick=7
    )


@pytest.mark.asyncio
async def test_updater_write_through_uses_port_without_session() -> None:
    """EmotionUpdater must call the injected port's write_emotion with no session arg."""
    store = EmotionStore()
    port = AsyncMock()
    updater = EmotionUpdater(emotion_store=store, writer=port)

    state = await updater.apply_dialogue_mood(npc_id="npc-1", mood_update="warm", tick=5)

    port.write_emotion.assert_awaited_once()
    call_kwargs = port.write_emotion.call_args[1]
    assert call_kwargs["npc_id"] == "npc-1"
    assert call_kwargs["tick"] == 5
    assert call_kwargs["valence"] == state.valence
    assert call_kwargs["arousal"] == state.arousal
    assert call_kwargs["label"] == state.label
