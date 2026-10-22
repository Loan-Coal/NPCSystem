"""
Package: graph.emotion
Layer: graph
Purpose: Emotion state and mood reads/writes.
Public surface: submodules — emotion_reader, emotion_writer, mood_queries (get_character_mood only).
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
