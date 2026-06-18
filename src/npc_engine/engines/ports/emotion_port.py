"""
Module: emotion_port
Layer: engines
Purpose: Structural Protocol for persisting NPC emotion scalars to the graph, so
         EmotionUpdater depends on one abstraction and holds no Neo4j session for
         its write-through (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, compute emotion values, or import graph functions.
Dependencies injected: none (pure interface).
Used by: engines/emotion/emotion_updater; implemented structurally by
         npc_engine.graph.repositories.emotion_repository.Neo4jEmotionRepository.
"""

from __future__ import annotations

from typing import Protocol


class EmotionGraphPort(Protocol):
    """Write-through access to an NPC's persisted emotion scalars."""

    async def write_emotion(
        self,
        *,
        npc_id: str,
        valence: int,
        arousal: int,
        label: str,
        tick: int,
    ) -> None:
        """Persist an NPC's valence/arousal/label/tick to its Character node."""
        ...
