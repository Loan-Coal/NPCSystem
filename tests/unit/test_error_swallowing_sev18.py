"""
Regression tests for SEV-18: replace silent error-swallowing with log-and-(re)raise.

Covers four engine sites:
  1. degradation._load_canned_text — corrupt YAML must log a warning
  2. memory_consolidation_engine — WITNESSED query failure must log a warning
  3. dialogue_handler._synthesize_audio — TTS failure must log + increment metric
  4. gossip_handler.run_tick — create_rumor failure must re-raise (not swallow)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.dialogue.degradation import _load_canned_text
from npc_engine.engines.gossip.gossip_handler import GossipHandler
from npc_engine.utils.metrics import get_counter_value, reset_metrics_registry


# ---------------------------------------------------------------------------
# 1. degradation._load_canned_text — corrupt YAML
# ---------------------------------------------------------------------------


def test_load_canned_text_logs_warning_on_corrupt_yaml(tmp_path):
    """_load_canned_text must log a warning when the YAML file is unreadable."""
    bad_yaml = tmp_path / "default.yaml"
    bad_yaml.write_text("key: [unclosed", encoding="utf-8")

    with patch("npc_engine.engines.dialogue.degradation._logger") as mock_logger:
        result = _load_canned_text("default", tmp_path)

    assert result == "I need a moment to think."
    mock_logger.warning.assert_called()
    assert any(
        "canned_response_load_failed" in call.args[0]
        for call in mock_logger.warning.call_args_list
    )


# ---------------------------------------------------------------------------
# 2. memory_consolidation_engine — WITNESSED query failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_witnessed_query_failure_logs_warning():
    """WITNESSED query failure must log a warning but still create the memory."""
    from npc_engine.engines.memory_consolidation.memory_consolidation_engine import (
        MemoryConsolidationEngine,
    )

    session = AsyncMock()
    session_store = MagicMock()
    session_store.get_all_turns_for_npc = AsyncMock(return_value=["turn1", "turn2", "turn3"])
    llm_client = AsyncMock()
    llm_client.generate = AsyncMock(return_value="summary text")

    engine = MemoryConsolidationEngine(
        session_store=session_store,
        llm_client=llm_client,
        graph_db=MagicMock(),  # SEV-08 made graph_db + settings required ctor params
        settings=MagicMock(),
        turn_threshold=2,
        clear_turns_after=False,
    )

    with (
        patch(
            "npc_engine.engines.memory_consolidation.memory_consolidation_engine.get_beliefs_for_character",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.memory_consolidation.memory_consolidation_engine.get_memories_for_character",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.memory_consolidation.memory_consolidation_engine.get_undisclosed_witnesses",
            new=AsyncMock(side_effect=RuntimeError("db error")),
        ),
        patch(
            "npc_engine.engines.memory_consolidation.memory_consolidation_engine.create_memory",
            new=AsyncMock(return_value="mem-001"),
        ),
        patch(
            "npc_engine.engines.memory_consolidation.memory_consolidation_engine._LOGGER"
        ) as mock_logger,
    ):
        result = await engine.consolidate(session=session, npc_id="npc_001", game_time=MagicMock())

    assert result == "mem-001"
    mock_logger.warning.assert_called_once()
    call_args = mock_logger.warning.call_args
    assert "witnessed_query_failed" in call_args.args[0]


# ---------------------------------------------------------------------------
# 3. dialogue_handler._synthesize_audio — TTS failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tts_failure_logs_warning_and_increments_metric():
    """TTS failure must log a warning and increment the tts_failures_total metric."""
    reset_metrics_registry()

    from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
    from npc_engine.engines.dialogue.dialogue_models import (
        ActionModel,
        DialogueResponse,
        FacialExpressionModel,
        RelationDeltas,
    )

    handler = DialogueHandler.__new__(DialogueHandler)
    tts_client = AsyncMock()
    tts_client.synthesize = AsyncMock(side_effect=RuntimeError("tts down"))
    handler._tts_client = tts_client

    emotion_updater = MagicMock()
    emotion_updater.get_state = AsyncMock(return_value=MagicMock())
    handler._emotion_updater = emotion_updater
    handler._session = AsyncMock()

    response = DialogueResponse(
        npc_response="Hello",
        relation_deltas=RelationDeltas(),
        action=ActionModel(),
        facial_expression=FacialExpressionModel(),
        degradation_level="full",
    )

    with (
        patch(
            "npc_engine.engines.dialogue.dialogue_handler.get_npc_voice_descriptor",
            new=AsyncMock(return_value="narrator"),
        ),
        patch(
            "npc_engine.engines.dialogue.dialogue_handler.modulate_voice",
            return_value=MagicMock(),
        ),
        patch("npc_engine.engines.dialogue.dialogue_handler._logger") as mock_logger,
    ):
        result = await handler._synthesize_audio(response=response, npc_id="npc_001")

    assert result is response
    mock_logger.warning.assert_called_once()
    call_args = mock_logger.warning.call_args
    assert "tts_failure" in call_args.args[0]
    assert get_counter_value("tts_failures_total") == 1.0


# ---------------------------------------------------------------------------
# 4. gossip_handler.run_tick — create_rumor failure must re-raise
# ---------------------------------------------------------------------------


def _make_gossip_settings(threshold: int = 0):
    s = MagicMock()
    s.GOSSIP_DISTORTION_BASE = 100.0
    s.RUMOR_DISTORTION_THRESHOLD = threshold
    s.RUMOR_EMOTION_SEVERITY_THRESHOLD = 999
    return s


def _make_gossip_session(severity: int = 80):
    session = AsyncMock()
    event_record = MagicMock()
    event_record.__getitem__ = lambda _s, k: {
        "event_id": "evt-1",
        "summary": "war breaks out",
        "severity": severity,
        "is_canonical": False,
    }[k]
    event_record.get = lambda k, default=None: {"is_canonical": False}.get(k, default)

    trust_record = MagicMock()
    trust_record.__getitem__ = lambda _s, k: {"trust": 50}[k]

    call_count = [0]

    async def _run_side(query, **kwargs):
        res = AsyncMock()
        if call_count[0] == 0:
            res.single = AsyncMock(return_value=event_record)
        else:
            res.single = AsyncMock(return_value=trust_record)
        call_count[0] += 1
        return res

    session.run = _run_side
    return session


@pytest.mark.asyncio
async def test_gossip_rumor_record_failure_reraises():
    """create_rumor failure must propagate — not be swallowed — out of run_tick."""
    handler = GossipHandler(
        settings=_make_gossip_settings(threshold=0),
        embedding_index=MagicMock(),
        weight_config=MagicMock(hostile_distortion_factor=1.0),
    )
    session = _make_gossip_session()

    sharer = {"id": "npc_a", "honesty": 10}
    receiver = {"id": "npc_b"}
    batch_row = [
        {
            "sharer_id": "npc_a",
            "receiver_id": "npc_b",
            "event_id": "evt-1",
            "summary": "war breaks out",
            "severity": 80,
            "is_canonical": False,
            "trust": 50,
            # L4-04: gossip_handler reads write["distortion_level"] to decide whether
            # to create_rumor. Omitting it made the guard never reach create_rumor, so
            # the re-raise it claims to test was never exercised. 100 >= threshold(0).
            "distortion_level": 100,
        }
    ]

    with (
        patch(
            "npc_engine.engines.gossip.gossip_handler.select_pairs",
            new=AsyncMock(return_value=[(sharer, receiver, MagicMock(), {"best_standing": None})]),
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.select_batch_event_trust",
            new=AsyncMock(return_value=batch_row),
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.write_batch_knowledge_propagation",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.create_rumor",
            new=AsyncMock(side_effect=RuntimeError("rumor db down")),
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely",
            new=AsyncMock(return_value=None),
        ),
    ):
        with pytest.raises(RuntimeError, match="rumor db down"):
            await handler.run_tick(session=session, tick_id=1)
