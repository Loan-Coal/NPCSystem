# EXP-13 — EmotionModelProtocol + VadEmotionModel (OCP seam for emotion)

**Phase:** 3 · **Effort:** M · **Deps:** none
**Touches:** `src/npc_engine/engines/emotion/emotion_updater.py`, new `src/npc_engine/engines/emotion/emotion_model_protocol.py`, new `src/npc_engine/engines/emotion/vad_emotion_model.py`
**Does NOT touch:** `demo_game/`, `emotion_state.py` (unchanged), `emotion_store.py` (unchanged), any graph layer, any prompt YAML, `EXPANSION_INDEX.md`

---

## Purpose

`emotion_updater.py:16-19` hard-codes shock divisors/caps as module constants; there is no
`EmotionModelProtocol` (`grep EmotionModelProtocol` → zero hits). Adding a new emotion
model (e.g. OCC appraisal, trait-modulated reactivity) requires editing the closed
`EmotionUpdater` class — an OCP violation flagged in `BUSINESS_INTENT.md:65` and L7-06.

First slice: **pure refactor + no behavior change.** Extract the computation logic into a
small `EmotionModelProtocol`, wrap the current VAD logic in a `VadEmotionModel` concrete
class, inject it into `EmotionUpdater` via `__init__`. All outputs must be byte-for-byte
identical.

---

## What already exists

- `emotion_updater.py:25`: `EmotionUpdater.__init__(emotion_store, decay_rate=2)` — DI
  seam already present; just need to add a model parameter.
- `emotion_updater.py:16-19`: `_SHOCK_VALENCE_DIVISOR = 3`, `_SHOCK_VALENCE_CAP = 30`,
  `_SHOCK_AROUSAL_DIVISOR = 2`, `_SHOCK_AROUSAL_CAP = 40` — these constants move into
  `VadEmotionModel`.
- `emotion_updater.py:35-58`: `apply_dialogue_mood` — applies a mood label + decay.
- `emotion_updater.py:71-96`: `apply_event_shock` — uses the 4 constants above.
- `emotion_updater.py:98-105`: `_decay` — uses `self._decay_rate`.
- `emotion_state.py:16-45`: `EmotionState` (frozen Pydantic), `derive_label` — both are
  data-only, stay unchanged, consumed by the model.

---

## Files

**New:**
- `src/npc_engine/engines/emotion/emotion_model_protocol.py` — `EmotionModelProtocol`
  (runtime_checkable Protocol with 3 methods; see shape below).
- `src/npc_engine/engines/emotion/vad_emotion_model.py` — `VadEmotionModel` (concrete
  implementation of the protocol, wrapping all logic currently in `EmotionUpdater`'s
  non-IO methods).
- `tests/unit/test_emotion_model_protocol.py` — unit tests.

**Edited:**
- `src/npc_engine/engines/emotion/emotion_updater.py` — inject `model: EmotionModelProtocol`
  (default `VadEmotionModel()`); delegate the computation steps to it; remove the 4
  module-level constants (they move into `VadEmotionModel`).

---

## Architecture fit

DIP strict: `EmotionUpdater.__init__` accepts `EmotionModelProtocol`, never
`VadEmotionModel` directly. Default is `VadEmotionModel()` so existing callers
(`dialogue_handler`, `gossip_handler`) require no changes. New models = new files.
Layer: `engines/emotion/` — no layer violations.

---

## Protocol shape

```python
# emotion_model_protocol.py
from __future__ import annotations
from typing import Protocol, runtime_checkable
from npc_engine.engines.emotion.emotion_state import EmotionState

@runtime_checkable
class EmotionModelProtocol(Protocol):
    """Compute emotion state transitions given events and decay."""

    def apply_shock(self, state: EmotionState, severity: int) -> EmotionState:
        """Apply emotional shock from a high-severity event."""
        ...

    def apply_mood_hint(self, state: EmotionState, mood_label: str, arousal_increment: int) -> EmotionState:
        """Apply a mood label hint (from dialogue output) to the existing state."""
        ...

    def decay(self, state: EmotionState, decay_rate: int) -> EmotionState:
        """Apply passive decay toward neutral."""
        ...
```

`VadEmotionModel` implements all three methods by directly porting the computations
from `EmotionUpdater._decay`, `apply_event_shock`, and `apply_dialogue_mood`.

---

## TDD

Write `tests/unit/test_emotion_model_protocol.py` FIRST.

All tests are pure Python — no I/O, no store mock needed (models are pure functions of
`EmotionState`).

| Test | What it asserts |
|------|-----------------|
| `test_vad_apply_shock_decreases_valence` | `apply_shock(EmotionState(), 60).valence < 0` |
| `test_vad_apply_shock_increases_arousal` | `apply_shock(EmotionState(), 60).arousal > 0` |
| `test_vad_apply_shock_bounded` | `apply_shock(EmotionState(valence=-90), 100).valence >= -100` |
| `test_vad_decay_moves_toward_neutral` | positive valence decays toward 0; arousal decreases |
| `test_vad_decay_does_not_overshoot` | valence does not cross 0 in a single step |
| `test_vad_apply_mood_hint_replaces_label` | `apply_mood_hint(state, "elated", 5).label == "elated"` |
| `test_vad_apply_mood_hint_increments_arousal` | arousal += 5, capped at 100 |
| `test_vad_protocol_conformance` | `isinstance(VadEmotionModel(), EmotionModelProtocol)` is True |
| `test_emotion_updater_uses_protocol_method` | monkeypatch model on `EmotionUpdater`; call `apply_event_shock`; assert model's `apply_shock` was called |
| `test_behavior_parity_shock` | Compare output of new `EmotionUpdater(store, model=VadEmotionModel())` vs old expected values for `severity=60` |

Run only: `pytest tests/unit/test_emotion_model_protocol.py -v`

---

## Done when

- `pytest tests/unit/test_emotion_model_protocol.py` green.
- Existing `pytest tests/unit/test_emotion_updater.py` (if it exists) still green — output
  identical to before.
- `EmotionUpdater.__init__` accepts `model: EmotionModelProtocol = VadEmotionModel()`.
- `EmotionUpdater` no longer contains the 4 `_SHOCK_*` module-level constants.
- `emotion_model_protocol.py` has module docstring + every method has docstring.
- `vad_emotion_model.py` has module docstring + class docstring + all methods documented.
- No file exceeds 300 lines.
- No behavior change observable via the protocol method outputs.
