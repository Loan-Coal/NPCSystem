"""
Package: graph.emotion
Layer: graph
Purpose: Emotion state and mood reads/writes.
Public surface: submodules — emotion_reader,emotion_writer,mood_queries.
Does NOT: orchestrate engine workflows or call LLMs.
Dependencies injected: None (graph data-access submodule package).
"""

from __future__ import annotations
