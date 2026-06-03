"""
Module: audio_player
Layer: demo_game
Purpose: Play raw WAV audio bytes via pygame.mixer. Called from the main game
         thread after the WS done event delivers TTS-synthesized speech.
         Errors are swallowed so a TTS outage never blocks gameplay.
Dependencies: pygame (pygame-ce), io (stdlib)
Used by: demo_game.game_controller
"""

from __future__ import annotations

import io

import pygame


def play_audio_bytes(data: bytes) -> None:
    """Play raw WAV audio bytes through pygame.mixer.

    No-op when: data is empty, the mixer is not initialised, or any pygame
    error occurs during Sound construction or playback.

    Args:
        data: Raw WAV audio bytes as returned by the TTS backend.
    """
    if not data:
        return
    if not pygame.mixer.get_init():
        return
    try:
        sound = pygame.mixer.Sound(file=io.BytesIO(data))
        sound.play()
    except Exception:
        return
