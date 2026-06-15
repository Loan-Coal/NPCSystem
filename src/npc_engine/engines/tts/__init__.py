"""
Package: tts
Layer: engines
Purpose: Text-to-speech adapters and emotion-to-voice-parameter modulation for NPC synthesis.
Does NOT: perform LLM calls or graph queries.
Dependencies injected: None.
Used by: dialogue_handler._synthesize_audio, api/dependencies.py
Public surface: TTSClientProtocol, VoiceParams, PiperAdapter, MockTTSAdapter, modulate
"""

from __future__ import annotations
