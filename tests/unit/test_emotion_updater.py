"""
Unit tests for EmotionUpdater.apply_event_shock.

Verifies severity-proportional valence/arousal shifts and label derivation.
"""

from __future__ import annotations

from npc_engine.engines.emotion.emotion_state import EmotionState, derive_label
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.emotion.emotion_updater import EmotionUpdater


def _make_updater(initial: EmotionState | None = None) -> EmotionUpdater:
    store = EmotionStore()
    updater = EmotionUpdater(emotion_store=store)
    if initial is not None:
        store.set(npc_id="npc-1", state=initial)
    return updater


def test_apply_event_shock_reduces_valence():
    """High-severity shock must decrease valence from neutral."""
    updater = _make_updater()
    state = updater.apply_event_shock(npc_id="npc-1", severity=90)
    assert state.valence < 0


def test_apply_event_shock_increases_arousal():
    """High-severity shock must increase arousal from resting state."""
    updater = _make_updater()
    state = updater.apply_event_shock(npc_id="npc-1", severity=90)
    assert state.arousal > 0


def test_apply_event_shock_proportional_to_severity():
    """Higher severity must produce a more negative valence than lower severity."""
    updater_low = _make_updater()
    updater_high = _make_updater()
    state_low = updater_low.apply_event_shock(npc_id="npc-1", severity=50)
    state_high = updater_high.apply_event_shock(npc_id="npc-1", severity=90)
    assert state_high.valence < state_low.valence


def test_apply_event_shock_capped_at_minus_100():
    """Valence must never drop below -100 even at maximum severity."""
    initial = EmotionState(valence=-90, arousal=0, label="melancholic")
    updater = _make_updater(initial=initial)
    state = updater.apply_event_shock(npc_id="npc-1", severity=100)
    assert state.valence >= -100


def test_apply_event_shock_persists_state():
    """Shock state must be persisted so get_state returns the shocked value."""
    updater = _make_updater()
    shocked = updater.apply_event_shock(npc_id="npc-1", severity=80)
    retrieved = updater.get_state(npc_id="npc-1")
    assert retrieved.valence == shocked.valence
    assert retrieved.arousal == shocked.arousal


def test_apply_event_shock_label_derived_correctly():
    """Label must be consistent with derive_label for the resulting valence/arousal."""
    updater = _make_updater()
    state = updater.apply_event_shock(npc_id="npc-1", severity=80)
    expected_label = derive_label(state.valence, state.arousal)
    assert state.label == expected_label


def test_apply_event_shock_zero_severity_no_change():
    """Zero severity must not change valence or arousal."""
    updater = _make_updater()
    state = updater.apply_event_shock(npc_id="npc-1", severity=0)
    assert state.valence == 0
    assert state.arousal == 0
