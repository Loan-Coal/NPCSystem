"""
Module: test_audio_player
Layer: demo_game (tests)
Purpose: Unit tests for demo_game.audio_player — pygame.mixer-based WAV playback.
         All pygame I/O is mocked so tests run headless.
Dependencies: demo_game.audio_player, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch, call

import pytest

from demo_game.audio_player import play_audio_bytes


_FAKE_WAV = b"RIFF\x00\x00\x00\x00WAVEfmt "


class TestPlayAudioBytes:
    def test_plays_sound_from_bytesio(self) -> None:
        """play_audio_bytes creates a Sound from BytesIO and calls play()."""
        mock_sound = MagicMock()
        with (
            patch("demo_game.audio_player.pygame.mixer.get_init", return_value=(44100, -16, 2)),
            patch("demo_game.audio_player.pygame.mixer.Sound", return_value=mock_sound) as mock_sound_cls,
        ):
            play_audio_bytes(_FAKE_WAV)

        mock_sound_cls.assert_called_once()
        file_arg = mock_sound_cls.call_args.kwargs.get("file") or mock_sound_cls.call_args.args[0]
        assert isinstance(file_arg, io.BytesIO)
        mock_sound.play.assert_called_once()

    def test_noop_when_mixer_not_initialised(self) -> None:
        """play_audio_bytes is silent when pygame mixer is not initialised (returns falsy)."""
        mock_sound_cls = MagicMock()
        with (
            patch("demo_game.audio_player.pygame.mixer.get_init", return_value=None),
            patch("demo_game.audio_player.pygame.mixer.Sound", mock_sound_cls),
        ):
            play_audio_bytes(_FAKE_WAV)  # must not raise

        mock_sound_cls.assert_not_called()

    def test_noop_on_empty_bytes(self) -> None:
        """play_audio_bytes with zero-length bytes does not attempt playback."""
        mock_sound_cls = MagicMock()
        with (
            patch("demo_game.audio_player.pygame.mixer.get_init", return_value=(44100, -16, 2)),
            patch("demo_game.audio_player.pygame.mixer.Sound", mock_sound_cls),
        ):
            play_audio_bytes(b"")

        mock_sound_cls.assert_not_called()

    def test_exception_during_playback_is_swallowed(self) -> None:
        """A pygame error during Sound construction does not propagate."""
        with (
            patch("demo_game.audio_player.pygame.mixer.get_init", return_value=(44100, -16, 2)),
            patch("demo_game.audio_player.pygame.mixer.Sound", side_effect=Exception("bad wav")),
        ):
            play_audio_bytes(_FAKE_WAV)  # must not raise
