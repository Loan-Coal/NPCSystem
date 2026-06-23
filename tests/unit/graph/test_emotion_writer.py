"""
Unit tests for EmotionGraphWriter.

Verifies that write_emotion issues correct Cypher parameters and uses MERGE.
All Neo4j I/O is mocked — no real DB required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.emotion.emotion_writer import EmotionGraphWriter


@pytest.mark.asyncio
async def test_write_emotion_sets_all_four_fields() -> None:
    """write_emotion must call session.run with all four emotion fields as params."""
    writer = EmotionGraphWriter()
    mock_session = MagicMock()
    mock_result = AsyncMock()
    mock_result.consume = AsyncMock()
    mock_session.run = AsyncMock(return_value=mock_result)

    await writer.write_emotion(
        session=mock_session,
        npc_id="npc-1",
        valence=42,
        arousal=30,
        label="warm",
        tick=7,
    )

    mock_session.run.assert_called_once()
    call_args, call_kwargs = mock_session.run.call_args

    all_params: dict = {}
    for v in call_args[1:]:
        if isinstance(v, dict):
            all_params.update(v)
    all_params.update(call_kwargs)

    assert all_params.get("valence") == 42, f"expected valence=42, got: {all_params}"
    assert all_params.get("arousal") == 30, f"expected arousal=30, got: {all_params}"
    assert all_params.get("mood_label") == "warm", f"expected mood_label='warm', got: {all_params}"
    assert all_params.get("tick") == 7, f"expected tick=7, got: {all_params}"


@pytest.mark.asyncio
async def test_write_emotion_uses_merge_not_create() -> None:
    """write_emotion must use MERGE in its Cypher query, not a bare CREATE."""
    writer = EmotionGraphWriter()
    mock_session = MagicMock()
    mock_result = AsyncMock()
    mock_result.consume = AsyncMock()
    mock_session.run = AsyncMock(return_value=mock_result)

    await writer.write_emotion(
        session=mock_session,
        npc_id="npc-2",
        valence=10,
        arousal=15,
        label="neutral",
        tick=1,
    )

    mock_session.run.assert_called_once()
    cypher_query: str = mock_session.run.call_args[0][0]
    assert "MERGE" in cypher_query, "Cypher must use MERGE for idempotency"
    assert "CREATE" not in cypher_query, "Cypher must not use bare CREATE"
