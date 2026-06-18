"""
Tests for relation_mutator.py — structured audit log events via DialogueGraphPort.

Verifies that apply_dialogue_relation_deltas:
- emits 'relation_delta_attempt' before the graph write
- emits 'relation_delta_applied' after a successful write
- delegates the actual graph write to the injected DialogueGraphPort (no session held)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.dialogue.dialogue_models import RelationDeltas
from npc_engine.engines.dialogue.relation_mutator import apply_dialogue_relation_deltas


@pytest.fixture()
def mock_repo() -> AsyncMock:
    """Provide a minimal DialogueGraphPort mock."""
    repo = AsyncMock()
    repo.apply_relation_deltas = AsyncMock(return_value=None)
    return repo


@pytest.fixture()
def mock_settings() -> MagicMock:
    """Provide a minimal Settings mock."""
    return MagicMock()


@pytest.mark.asyncio
async def test_apply_delta_logs_attempt_and_success(
    mock_repo: AsyncMock,
    mock_settings: MagicMock,
) -> None:
    """Successful apply emits relation_delta_attempt and relation_delta_applied."""
    deltas = RelationDeltas(trust=5, affection=3)
    with patch("npc_engine.engines.dialogue.relation_mutator._LOGGER") as mock_logger:
        await apply_dialogue_relation_deltas(
            mock_repo, mock_settings, "npc_1", "player_1", deltas, "cause_A", 42
        )
    info_events = [call.args[0] for call in mock_logger.info.call_args_list]
    assert "relation_delta_attempt" in info_events
    assert "relation_delta_applied" in info_events


@pytest.mark.asyncio
async def test_apply_delta_delegates_to_port(
    mock_repo: AsyncMock,
    mock_settings: MagicMock,
) -> None:
    """apply_dialogue_relation_deltas delegates the write to the port."""
    deltas = RelationDeltas(trust=5, affection=3)
    with patch("npc_engine.engines.dialogue.relation_mutator._LOGGER"):
        await apply_dialogue_relation_deltas(
            mock_repo, mock_settings, "npc_1", "player_1", deltas, "cause_A", 42
        )
    mock_repo.apply_relation_deltas.assert_awaited_once_with(
        npc_id="npc_1",
        player_id="player_1",
        relation_deltas=deltas,
        cause_id="cause_A",
        tick_id=42,
        settings=mock_settings,
    )
