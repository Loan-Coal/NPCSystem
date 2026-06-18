"""
Module: trait_modulated_model
Layer: engines
Purpose: EmotionModelProtocol implementation that scales VAD deltas by NPC personality traits.
         A timid NPC (high fear_sensitivity) receives larger negative-valence / higher-arousal
         shifts from shocks; neutral traits (all 1.0) reproduce VadEmotionModel exactly.

Does NOT:
  - Access the graph or any database.
  - Call LLMs or any external service.
  - Manage or persist emotion state.

Dependencies injected:
  - traits: dict[str, float] — caller-supplied trait multipliers keyed by trait name.
    The caller (e.g. EmotionUpdater) is responsible for fetching traits from the graph
    and passing them here.
"""
from __future__ import annotations

from npc_engine.engines.emotion.emotion_model_protocol import EmotionModelProtocol
from npc_engine.engines.emotion.emotion_state import EmotionState, derive_label

# ---------------------------------------------------------------------------
# Trait keys — callers must use these names when building the traits dict.
# ---------------------------------------------------------------------------
TRAIT_FEAR_SENSITIVITY = "fear_sensitivity"
TRAIT_ANGER_SENSITIVITY = "anger_sensitivity"
TRAIT_JOY_SENSITIVITY = "joy_sensitivity"

# Default multiplier applied when a trait key is absent from the provided dict.
_DEFAULT_TRAIT_MULTIPLIER: float = 1.0

# Clamp bounds for trait multipliers — prevents runaway amplification.
_TRAIT_MIN: float = 0.0
_TRAIT_MAX: float = 5.0

# Shock arithmetic constants (mirror VadEmotionModel so neutral traits reproduce it).
_SHOCK_VALENCE_DIVISOR: int = 3
_SHOCK_VALENCE_CAP: int = 30
_SHOCK_AROUSAL_DIVISOR: int = 2
_SHOCK_AROUSAL_CAP: int = 40

_AROUSAL_MAX: int = 100
_AROUSAL_MIN: int = 0

# Label inertia: same threshold as VadEmotionModel (LSP parity).
_MIN_AROUSAL_TO_SHIFT_LABEL: int = 20


class TraitModulatedEmotionModel:
    """EmotionModelProtocol implementation that scales VAD deltas by personality traits.

    Shock deltas are multiplied by the NPC's ``fear_sensitivity`` trait so that
    timid NPCs experience stronger emotional responses to negative events.  With
    all trait multipliers set to 1.0 the output is identical to VadEmotionModel
    (LSP parity guarantee).

    All methods are pure — no I/O, no mutable state.

    Args:
        traits: Mapping of trait name to float multiplier.  Missing keys fall
                back to ``_DEFAULT_TRAIT_MULTIPLIER`` (1.0).  Values are clamped
                to [0.0, 5.0] to prevent runaway amplification.
    """

    def __init__(self, traits: dict[str, float]) -> None:
        """Store trait multipliers, clamping each to the safe range.

        Args:
            traits: Caller-supplied personality trait multipliers.
        """
        self._traits: dict[str, float] = {
            k: max(_TRAIT_MIN, min(_TRAIT_MAX, v)) for k, v in traits.items()
        }

    def _trait(self, key: str) -> float:
        """Return the clamped multiplier for *key*, defaulting to 1.0.

        Args:
            key: One of the TRAIT_* module-level constants.

        Returns:
            Clamped float multiplier in [_TRAIT_MIN, _TRAIT_MAX].
        """
        return self._traits.get(key, _DEFAULT_TRAIT_MULTIPLIER)

    def apply_shock(self, state: EmotionState, severity: int) -> EmotionState:
        """Apply trait-scaled emotional shock from a high-severity event.

        Valence drop and arousal rise are each multiplied by the NPC's
        ``fear_sensitivity`` trait.  Neutral traits (1.0) reproduce the
        VadEmotionModel result exactly.

        Args:
            state: Current emotion state before the shock.
            severity: Event severity 0–100; values below 50 produce small shifts.

        Returns:
            New EmotionState with valence decreased and arousal increased,
            both clamped to their valid ranges.
        """
        fear_mult = self._trait(TRAIT_FEAR_SENSITIVITY)

        raw_valence_delta = min(_SHOCK_VALENCE_CAP, severity // _SHOCK_VALENCE_DIVISOR)
        raw_arousal_delta = min(_SHOCK_AROUSAL_CAP, severity // _SHOCK_AROUSAL_DIVISOR)

        scaled_valence_delta = int(raw_valence_delta * fear_mult)
        scaled_arousal_delta = int(raw_arousal_delta * fear_mult)

        new_valence = max(-100, state.valence - scaled_valence_delta)
        new_arousal = min(_AROUSAL_MAX, state.arousal + scaled_arousal_delta)
        return EmotionState(
            valence=new_valence,
            arousal=new_arousal,
            label=derive_label(new_valence, new_arousal),
        )

    def apply_mood_hint(
        self,
        state: EmotionState,
        mood_label: str,
        arousal_increment: int,
    ) -> EmotionState:
        """Apply a mood label hint, preserving label inertia below threshold.

        Identical to VadEmotionModel; traits do not modulate mood hints in
        this slice (future slice can add joy_sensitivity scaling).

        Args:
            state: Current emotion state.
            mood_label: Candidate new label from LLM dialogue output.
            arousal_increment: Amount to add to arousal (capped at 100).

        Returns:
            New EmotionState with updated arousal; label replaced only when
            arousal >= _MIN_AROUSAL_TO_SHIFT_LABEL.
        """
        new_arousal = min(_AROUSAL_MAX, state.arousal + arousal_increment)
        if new_arousal < _MIN_AROUSAL_TO_SHIFT_LABEL:
            effective_label = state.label
        else:
            effective_label = mood_label
        return EmotionState(
            valence=state.valence,
            arousal=new_arousal,
            label=effective_label,
        )

    def decay(self, state: EmotionState, decay_rate: int) -> EmotionState:
        """Move valence and arousal toward neutral without overshooting.

        Traits do not modulate decay in this slice.

        Args:
            state: Current emotion state.
            decay_rate: Absolute units per tick that valence and arousal
                approach zero.

        Returns:
            New EmotionState with valence and arousal moved closer to neutral.
        """
        valence = state.valence
        if valence > 0:
            valence = max(0, valence - decay_rate)
        elif valence < 0:
            valence = min(0, valence + decay_rate)
        arousal = max(_AROUSAL_MIN, state.arousal - decay_rate)
        return EmotionState(
            valence=valence,
            arousal=arousal,
            label=derive_label(valence, arousal),
        )


# Confirm protocol conformance at import time.
assert isinstance(TraitModulatedEmotionModel({}), EmotionModelProtocol)
