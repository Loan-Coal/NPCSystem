"""
Module: emotion_bootstrap_port
Layer: engines
Purpose: Structural Protocol for reading persisted emotion fields from the graph at
         startup. EmotionBootstrapper depends on this Protocol instead of importing
         graph functions directly or receiving an AsyncSession (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, compute emotion arithmetic, or call LLMs.
Dependencies injected: none (pure interface).
Used by: engines/emotion/emotion_bootstrap.EmotionBootstrapper;
         implemented structurally by
         graph/repositories/emotion_bootstrap_repository.Neo4jEmotionBootstrapRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class EmotionBootstrapGraphPort(Protocol):
    """Reads persisted emotion fields for one NPC from the graph at startup."""

    async def get_emotion_fields(self, npc_id: str) -> dict[str, Any] | None:
        """Return the emotion fields stored on the character node, or None.

        Args:
            npc_id: NPC character ID.

        Returns:
            Dict with keys ``emotion_valence``, ``emotion_arousal``,
            ``emotion_mood_label`` (values may be None), or None when the
            character node does not exist.
        """
        ...
