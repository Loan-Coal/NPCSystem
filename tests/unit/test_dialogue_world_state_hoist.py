"""
test_dialogue_world_state_hoist.py - Unit tests for the single world-state fetch
hoist in DialogueHandler (ISSUE-087: avoid the double get_world_state read when
both the arousal and knowledge branches fire on one turn).

Does NOT: connect to Neo4j or any external service (get_world_state is patched).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler


def _make_handler(*, knowledge_engine: object | None = None, knowledge_enabled: bool = False) -> DialogueHandler:
    handler = DialogueHandler.__new__(DialogueHandler)
    handler._knowledge_engine = knowledge_engine  # type: ignore[attr-defined]
    handler._settings = SimpleNamespace(KNOWLEDGE_LEARNING_ENABLED=knowledge_enabled, WORLD_ID="world")  # type: ignore[attr-defined]
    handler._session = object()  # type: ignore[attr-defined]
    return handler


def test_needs_world_state_true_for_high_arousal():
    handler = _make_handler()
    response = SimpleNamespace(learned_facts=())
    new_emotion = SimpleNamespace(arousal=85)
    assert handler._needs_world_state(response=response, new_emotion=new_emotion) is True


def test_needs_world_state_false_when_neither_branch_fires():
    handler = _make_handler()
    response = SimpleNamespace(learned_facts=())
    new_emotion = SimpleNamespace(arousal=10)
    assert handler._needs_world_state(response=response, new_emotion=new_emotion) is False


def test_needs_world_state_true_for_learned_facts():
    handler = _make_handler(knowledge_engine=object(), knowledge_enabled=True)
    response = SimpleNamespace(learned_facts=("the bridge is out",))
    new_emotion = SimpleNamespace(arousal=10)
    assert handler._needs_world_state(response=response, new_emotion=new_emotion) is True


@pytest.mark.asyncio
async def test_maybe_load_world_state_fetches_once_when_both_branches_fire():
    handler = _make_handler(knowledge_engine=object(), knowledge_enabled=True)
    response = SimpleNamespace(learned_facts=("a fact",))
    new_emotion = SimpleNamespace(arousal=85)
    with patch(
        "npc_engine.engines.dialogue.dialogue_handler.get_world_state",
        new=AsyncMock(return_value=SimpleNamespace()),
    ) as mock_get:
        result = await handler._maybe_load_world_state(response=response, new_emotion=new_emotion)
    assert result is not None
    mock_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_maybe_load_world_state_skips_fetch_when_no_branch_fires():
    handler = _make_handler()
    response = SimpleNamespace(learned_facts=())
    new_emotion = SimpleNamespace(arousal=10)
    with patch(
        "npc_engine.engines.dialogue.dialogue_handler.get_world_state",
        new=AsyncMock(return_value=SimpleNamespace()),
    ) as mock_get:
        result = await handler._maybe_load_world_state(response=response, new_emotion=new_emotion)
    assert result is None
    mock_get.assert_not_awaited()
