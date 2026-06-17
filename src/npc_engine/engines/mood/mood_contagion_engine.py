"""
Module: mood_contagion_engine
Layer: engines
Purpose: Spreads emotional states between co-located, affectionate NPC pairs each tick.
Does NOT: write emotion state to EmotionStore directly, open sessions, or import the
          graph layer — delegates graph access to the injected MoodGraphPort.
Dependencies: engines/emotion/emotion_store, engines/emotion/emotion_state, engines/ports/mood_port
Dependencies injected: EmotionStore, MoodGraphPort (via __init__).
Used by: scheduler/tick_scheduler, api/dependency_singletons
"""

from __future__ import annotations

import logging

from npc_engine.engines.emotion.emotion_state import EmotionState, derive_label
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.ports.mood_port import MoodGraphPort

LOGGER = logging.getLogger(__name__)

_BLEND_WEIGHT = 0.1
_AFFECTION_THRESHOLD = 50

_LABEL_TO_VALENCE_AROUSAL: dict[str, tuple[int, int]] = {
    "elated": (60, 80),
    "warm": (50, 40),
    "neutral": (0, 20),
    "melancholic": (-50, 30),
    "agitated": (-60, 80),
}


class MoodContagionEngine:
    """Blends NPC mood states for co-located pairs with affection > threshold each tick.

    On each tick:
    1. Fetch co-located NPC pairs whose RELATES_TO.affection exceeds the threshold.
    2. For each pair, blend valence and arousal: new_a = 0.9 * a + 0.1 * b (immutable).
    3. Update EmotionStore and persist new mood label + intensity to the CHARACTER node.

    On startup, call ``initialize()`` to load persisted moods from Neo4j into
    the EmotionStore so mood history survives server restarts.

    Graph access is injected as a MoodGraphPort (DEC-122 / SEV-24); the engine holds
    no Neo4j session. The tick scheduler's ``session`` kwarg is accepted and ignored
    until the BaseEngine protocol drops it.
    """

    def __init__(
        self,
        emotion_store: EmotionStore,
        mood_repo: MoodGraphPort,
        affection_threshold: int = _AFFECTION_THRESHOLD,
    ) -> None:
        """Initialise the engine.

        Args:
            emotion_store: Shared in-memory emotion state store.
            mood_repo: Graph access port (read moods/pairs, write mood).
            affection_threshold: Minimum RELATES_TO.affection for contagion to apply.
        """
        self._store = emotion_store
        self._mood_repo = mood_repo
        self._affection_threshold = affection_threshold

    async def initialize(self) -> int:
        """Load persisted mood states from Neo4j into EmotionStore.

        Call once on server startup before the first tick.

        Returns:
            Number of character moods loaded.
        """
        rows = await self._mood_repo.get_all_character_moods()
        for row in rows:
            char_id = row["character_id"]
            label = row["mood"]
            intensity = row["intensity"]
            valence, arousal = _label_to_state(label, intensity)
            state = EmotionState(valence=valence, arousal=arousal, label=label)
            await self._store.set(npc_id=char_id, state=state)
        LOGGER.info("MoodContagionEngine: loaded %d moods from Neo4j", len(rows))
        return len(rows)

    async def run_tick(self, *, tick_id: int) -> dict:
        """Blend moods for co-located affectionate pairs and persist results.

        Args:
            tick_id: Current game tick identifier.
            **_: Absorbs the scheduler's ``session`` kwarg (unused; see class docstring).

        Returns:
            Dict with ``tick_id`` and ``affected`` (number of NPC pairs blended).
        """
        pairs = await self._mood_repo.get_co_located_affectionate_pairs(
            affection_threshold=self._affection_threshold
        )

        affected = 0
        for npc_a, npc_b in pairs:
            state_a = await self._store.get(npc_a)
            state_b = await self._store.get(npc_b)

            new_a = _blend(state_a, state_b)
            new_b = _blend(state_b, state_a)

            await self._store.set(npc_id=npc_a, state=new_a)
            await self._store.set(npc_id=npc_b, state=new_b)

            await self._mood_repo.set_character_mood(
                character_id=npc_a,
                mood=new_a.label,
                intensity=new_a.arousal / 100.0,
            )
            await self._mood_repo.set_character_mood(
                character_id=npc_b,
                mood=new_b.label,
                intensity=new_b.arousal / 100.0,
            )
            affected += 1

        LOGGER.debug("MoodContagionEngine tick=%d affected_pairs=%d", tick_id, affected)
        return {"tick_id": tick_id, "affected": affected}


def _blend(source: EmotionState, other: EmotionState) -> EmotionState:
    """Return a new EmotionState with source blended toward other by _BLEND_WEIGHT.

    Args:
        source: The NPC whose state is being updated.
        other: The NPC whose state influences source.

    Returns:
        New immutable EmotionState.
    """
    new_valence = int(round((1 - _BLEND_WEIGHT) * source.valence + _BLEND_WEIGHT * other.valence))
    new_arousal = int(round((1 - _BLEND_WEIGHT) * source.arousal + _BLEND_WEIGHT * other.arousal))
    new_valence = max(-100, min(100, new_valence))
    new_arousal = max(0, min(100, new_arousal))
    return EmotionState(
        valence=new_valence,
        arousal=new_arousal,
        label=derive_label(new_valence, new_arousal),
    )


def _label_to_state(label: str, intensity: float) -> tuple[int, int]:
    """Reconstruct approximate (valence, arousal) from a stored label and intensity.

    Uses intensity (arousal/100) to scale the canonical values for the label.

    Args:
        label: Mood label string.
        intensity: Stored intensity in [0.0, 1.0].

    Returns:
        Tuple of (valence, arousal) integers.
    """
    base_valence, base_arousal = _LABEL_TO_VALENCE_AROUSAL.get(label, (0, 20))
    arousal = int(round(intensity * 100))
    return base_valence, arousal
