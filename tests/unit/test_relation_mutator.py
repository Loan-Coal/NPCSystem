"""
Tests for relation_mutator.py — structured audit log events.

Verifies that apply_dialogue_relation_deltas emits:
- 'relation_delta_attempt' before the graph write
- 'relation_delta_applied' after a successful write
- 'relation_edge_missing' warning when RelationEdgeNotFoundError is raised
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.dialogue.dialogue_models import RelationDeltas
from npc_engine.engines.dialogue.relation_mutator import apply_dialogue_relation_deltas
from npc_engine.utils.errors import RelationEdgeNotFoundError


@pytest.fixture()
def mock_session() -> AsyncMock:
    """Provide a minimal async Neo4j session mock."""
    return AsyncMock()


@pytest.fixture()
def mock_settings() -> MagicMock:
    """Provide a minimal Settings mock."""
    return MagicMock()


@pytest.mark.asyncio
async def test_apply_delta_logs_attempt_and_success(
    mock_session: AsyncMock,
    mock_settings: MagicMock,
) -> None:
    """Successful apply emits relation_delta_attempt and relation_delta_applied."""
    deltas = RelationDeltas(trust=5, affection=3)
    with patch("npc_engine.engines.dialogue.relation_mutator._LOGGER") as mock_logger:
        with patch(
            "npc_engine.engines.dialogue.relation_mutator.apply_relation_delta",
            new_callable=AsyncMock,
        ) as mock_ard:
            mock_ard.return_value = None
            await apply_dialogue_relation_deltas(
                mock_session, mock_settings, "npc_1", "player_1", deltas, "cause_A", 42
            )
    info_events = [call.args[0] for call in mock_logger.info.call_args_list]
    assert "relation_delta_attempt" in info_events
    assert "relation_delta_applied" in info_events


@pytest.mark.asyncio
async def test_apply_delta_logs_warning_on_missing_edge(
    mock_session: AsyncMock,
    mock_settings: MagicMock,
) -> None:
    """Missing edge emits relation_edge_missing warning and does not re-raise."""
    deltas = RelationDeltas(trust=5, affection=3)
    with patch("npc_engine.engines.dialogue.relation_mutator._LOGGER") as mock_logger:
        with patch(
            "npc_engine.engines.dialogue.relation_mutator.apply_relation_delta",
            new_callable=AsyncMock,
        ) as mock_ard:
            mock_ard.side_effect = RelationEdgeNotFoundError(src_id="npc_1", dst_id="player_1")
            await apply_dialogue_relation_deltas(
                mock_session, mock_settings, "npc_1", "player_1", deltas, "cause_A", 42
            )
    warning_events = [call.args[0] for call in mock_logger.warning.call_args_list]
    assert "relation_edge_missing" in warning_events
