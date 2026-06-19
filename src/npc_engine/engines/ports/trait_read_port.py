"""
Module: trait_read_port
Layer: engines
Purpose: Structural Protocol for per-NPC personality trait reads so EmotionUpdater can
         fetch trait multipliers without holding a Neo4j session (DIP/ISSUE-096/DEC-137).
Does NOT: open sessions, run Cypher, compute emotion deltas, or import graph functions.
Dependencies injected: none (pure interface).
Used by: engines/emotion/emotion_updater (via optional constructor injection);
         implemented structurally by the graph.repositories layer (slice 2 wiring).
"""

from __future__ import annotations

from typing import Protocol


class TraitReadPort(Protocol):
    """Read-only access to per-NPC personality trait multipliers."""

    async def get_npc_traits(self, *, npc_id: str) -> dict[str, float]:
        """Return personality trait multipliers for the NPC, keyed by trait name.

        Args:
            npc_id: Unique NPC identifier.

        Returns:
            Mapping of trait name (e.g. ``"fear_sensitivity"``) to float multiplier.
            Returns an empty dict when no traits are recorded for the NPC; callers
            must fall back to neutral (1.0) defaults for missing keys.
        """
        ...
