"""
Module: test_dialogue_ws_route
Layer: tests/unit
Purpose: Unit tests for src/npc_engine/api/routes/dialogue_ws — verifies the
         WebSocket route assembles the done message correctly, including base64
         audio when TTS produces audio_bytes.
Dependencies: npc_engine.api.routes.dialogue_ws, unittest.mock
Used by: make test
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.dialogue.dialogue_models import (
    ActionModel,
    DialogueResponse,
    FacialExpressionModel,
    RelationDeltas,
)


def _make_response(audio_bytes: bytes | None = None) -> DialogueResponse:
    """Build a minimal DialogueResponse, optionally with audio."""
    return DialogueResponse(
        npc_response="Hello traveller.",
        relation_deltas=RelationDeltas(),
        mood_update="calm",
        action=ActionModel(),
        facial_expression=FacialExpressionModel(),
        session_id="p:n",
        degradation_level="full",
        audio_bytes=audio_bytes,
    )


class TestDialogueWsRouteAudio:
    """done message includes audio_bytes_b64 when handler returns audio."""

    def test_done_message_includes_audio_bytes_b64_when_present(self) -> None:
        """When handler.handle() returns audio_bytes, done data must include audio_bytes_b64."""
        from npc_engine.api.routes.dialogue_ws import _build_done_data

        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt "
        response = _make_response(audio_bytes=wav_bytes)
        data = _build_done_data(response)

        assert "audio_bytes_b64" in data
        decoded = base64.b64decode(data["audio_bytes_b64"])
        assert decoded == wav_bytes

    def test_done_message_audio_bytes_b64_is_none_when_absent(self) -> None:
        """When handler returns no audio, audio_bytes_b64 is None in done data."""
        from npc_engine.api.routes.dialogue_ws import _build_done_data

        response = _make_response(audio_bytes=None)
        data = _build_done_data(response)

        assert data["audio_bytes_b64"] is None

    def test_done_message_contains_standard_fields(self) -> None:
        """done data always contains degradation_level, emotion, relation_deltas, action, facial_expression."""
        from npc_engine.api.routes.dialogue_ws import _build_done_data

        response = _make_response()
        data = _build_done_data(response)

        for key in ("degradation_level", "emotion", "relation_deltas", "action", "facial_expression"):
            assert key in data, f"Missing key: {key}"
