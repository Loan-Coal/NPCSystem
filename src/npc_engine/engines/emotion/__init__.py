"""
emotion package - Persistent NPC emotion state helpers.
Layer: engines
Purpose: Persistent per-NPC VAD emotion state (valence/arousal/label) with decay and
         dialogue/event-driven updates, injected into dialogue context for in-character tone.
Public surface: (list re-exports here)

Does NOT: control animation rendering.

Dependencies injected: None.
"""

from __future__ import annotations
