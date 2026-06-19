"""
Module: emotion_model_factory
Layer: engines
Purpose: Registry + factory for EmotionModelProtocol implementations. New models
         register via register_emotion_model(name, ctor) without editing existing
         code (OCP). build_emotion_model dispatches via the registry.
Does NOT: fetch per-NPC traits from the graph (deferred — see ISSUES), perform I/O,
          or hold state.
Dependencies injected: Settings (only EMOTION_MODEL is read).
Used by: api/dependencies_stores.get_emotion_updater.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

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

# Registry of zero-arg constructors keyed by EMOTION_MODEL name.
# Add new models via register_emotion_model; never edit this dict directly.
_EMOTION_REGISTRY: dict[str, Callable[[], EmotionModelProtocol]] = {}


def register_emotion_model(
    name: str, constructor: Callable[[], EmotionModelProtocol]
) -> None:
    """Register an emotion model constructor under *name*.

    Args:
        name: The EMOTION_MODEL config value that selects this model.
        constructor: Zero-arg callable returning an EmotionModelProtocol instance.
    """
    _EMOTION_REGISTRY[name] = constructor


def registered_emotion_models() -> frozenset[str]:
    """Return the names of all currently-registered emotion models.

    Returns:
        Frozenset of registered model names (single source of truth for config
        validation — mirrors registered_backends() in engines/llm/factory.py).
    """
    return frozenset(_EMOTION_REGISTRY)


def build_emotion_model(settings: Settings) -> EmotionModelProtocol:
    """Return the EmotionModelProtocol implementation selected by settings.

    Args:
        settings: Application settings; ``EMOTION_MODEL`` selects the backend via
            the registry (e.g. "vad" → VadEmotionModel).

    Returns:
        A protocol-conforming emotion model ready to inject into EmotionUpdater.

    Raises:
        ValueError: When settings.EMOTION_MODEL names an unregistered model.
    """
    constructor = _EMOTION_REGISTRY.get(settings.EMOTION_MODEL)
    if constructor is None:
        raise ValueError(
            f"Unknown emotion model {settings.EMOTION_MODEL!r}; "
            f"registered: {sorted(registered_emotion_models())}"
        )
    return constructor()


# ---------------------------------------------------------------------------
# Built-in registrations (add new models below — never remove existing ones)
# ---------------------------------------------------------------------------

register_emotion_model("vad", VadEmotionModel)
register_emotion_model(
    "trait_modulated",
    lambda: TraitModulatedEmotionModel(traits=dict(_DEMO_DEFAULT_TRAITS)),
)
