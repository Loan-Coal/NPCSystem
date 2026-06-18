"""
Module: emotion_model_factory
Layer: engines
Purpose: Build the configured EmotionModelProtocol implementation (VAD baseline or
         trait-modulated) from application settings, so the composition root can
         select the emotion model without importing concrete classes (DIP / OCP).
Does NOT: fetch per-NPC traits from the graph (deferred — see ISSUES), perform I/O,
          or hold state.
Dependencies injected: Settings (only EMOTION_MODEL is read).
Used by: api/dependencies_stores.get_emotion_updater.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from npc_engine.engines.emotion.emotion_model_protocol import EmotionModelProtocol
from npc_engine.engines.emotion.trait_modulated_model import (
    TRAIT_ANGER_SENSITIVITY,
    TRAIT_FEAR_SENSITIVITY,
    TRAIT_JOY_SENSITIVITY,
    TraitModulatedEmotionModel,
)
from npc_engine.engines.emotion.vad_emotion_model import VadEmotionModel

if TYPE_CHECKING:
    from npc_engine.config import Settings

# Demo-tuned default trait multipliers used when the trait-modulated model is
# selected without per-NPC traits (per-NPC trait fetch is a deferred slice).
# fear > 1.0 makes shocks visibly stronger than the VAD baseline so the wiring
# is demonstrable in a live tick.
_DEMO_DEFAULT_TRAITS: dict[str, float] = {
    TRAIT_FEAR_SENSITIVITY: 1.5,
    TRAIT_ANGER_SENSITIVITY: 1.2,
    TRAIT_JOY_SENSITIVITY: 1.0,
}


def build_emotion_model(settings: Settings) -> EmotionModelProtocol:
    """Return the EmotionModelProtocol implementation selected by settings.

    Args:
        settings: Application settings; ``EMOTION_MODEL`` selects the backend
            ("vad" → VadEmotionModel, "trait_modulated" → TraitModulatedEmotionModel
            seeded with demo-default trait multipliers).

    Returns:
        A protocol-conforming emotion model ready to inject into EmotionUpdater.
    """
    if settings.EMOTION_MODEL == "trait_modulated":
        return TraitModulatedEmotionModel(traits=dict(_DEMO_DEFAULT_TRAITS))
    return VadEmotionModel()
