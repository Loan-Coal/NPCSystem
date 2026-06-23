"""
Unit tests for EmotionUpdater.apply_event_shock and per-NPC trait injection (ISSUE-096).

Verifies severity-proportional valence/arousal shifts, label derivation,
and that an injected TraitReadPort provides per-NPC trait multipliers to
TraitModulatedEmotionModel so different NPCs receive different shock magnitudes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.emotion.emotion_state import EmotionState, derive_label
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.emotion.emotion_updater import EmotionUpdater
from npc_engine.engines.emotion.trait_modulated_model import TRAIT_FEAR_SENSITIVITY


async def _make_updater(initial: EmotionState | None = None) -> EmotionUpdater:
    store = EmotionStore()
    updater = EmotionUpdater(emotion_store=store)
    if initial is not None:
        await store.set(npc_id="npc-1", state=initial)
    return updater


@pytest.mark.asyncio
async def test_apply_event_shock_reduces_valence():
    """High-severity shock must decrease valence from neutral."""
    updater = await _make_updater()
    state = await updater.apply_event_shock(npc_id="npc-1", severity=90)
    assert state.valence < 0


@pytest.mark.asyncio
async def test_apply_event_shock_increases_arousal():
    """High-severity shock must increase arousal from resting state."""
    updater = await _make_updater()
    state = await updater.apply_event_shock(npc_id="npc-1", severity=90)
    assert state.arousal > 0


@pytest.mark.asyncio
async def test_apply_event_shock_proportional_to_severity():
    """Higher severity must produce a more negative valence than lower severity."""
    updater_low = await _make_updater()
    updater_high = await _make_updater()
    state_low = await updater_low.apply_event_shock(npc_id="npc-1", severity=50)
    state_high = await updater_high.apply_event_shock(npc_id="npc-1", severity=90)
    assert state_high.valence < state_low.valence


@pytest.mark.asyncio
async def test_apply_event_shock_capped_at_minus_100():
    """Valence must never drop below -100 even at maximum severity."""
    initial = EmotionState(valence=-90, arousal=0, label="melancholic")
    updater = await _make_updater(initial=initial)
    state = await updater.apply_event_shock(npc_id="npc-1", severity=100)
    assert state.valence >= -100


@pytest.mark.asyncio
async def test_apply_event_shock_persists_state():
    """Shock state must be persisted so get_state returns the shocked value."""
    updater = await _make_updater()
    shocked = await updater.apply_event_shock(npc_id="npc-1", severity=80)
    retrieved = await updater.get_state(npc_id="npc-1")
    assert retrieved.valence == shocked.valence
    assert retrieved.arousal == shocked.arousal


@pytest.mark.asyncio
async def test_apply_event_shock_label_derived_correctly():
    """Label must be consistent with derive_label for the resulting valence/arousal."""
    updater = await _make_updater()
    state = await updater.apply_event_shock(npc_id="npc-1", severity=80)
    expected_label = derive_label(state.valence, state.arousal)
    assert state.label == expected_label


@pytest.mark.asyncio
async def test_apply_event_shock_zero_severity_no_change():
    """Zero severity must not change valence or arousal."""
    updater = await _make_updater()
    state = await updater.apply_event_shock(npc_id="npc-1", severity=0)
    assert state.valence == 0
    assert state.arousal == 0


# ---------------------------------------------------------------------------
# ISSUE-096: per-NPC traits via TraitReadPort
# ---------------------------------------------------------------------------


def _make_trait_reader(traits_by_npc: dict[str, dict[str, float]]) -> MagicMock:
    """Return a mock TraitReadPort that returns per-NPC trait dicts."""
    reader = MagicMock()
    async def _get(*, npc_id: str) -> dict[str, float]:
        return traits_by_npc.get(npc_id, {})
    reader.get_npc_traits = _get
    return reader


@pytest.mark.asyncio
async def test_trait_reader_amplifies_shock_for_fearful_npc() -> None:
    """ISSUE-096: fearful NPC (fear_sensitivity=2.0) receives a larger valence drop
    than a neutral NPC (fear_sensitivity=1.0) for the same shock severity."""
    store_fearful = EmotionStore()
    store_neutral = EmotionStore()

    fearful_reader = _make_trait_reader({"npc-fearful": {TRAIT_FEAR_SENSITIVITY: 2.0}})
    neutral_reader = _make_trait_reader({"npc-neutral": {TRAIT_FEAR_SENSITIVITY: 1.0}})

    updater_fearful = EmotionUpdater(emotion_store=store_fearful, trait_reader=fearful_reader)
    updater_neutral = EmotionUpdater(emotion_store=store_neutral, trait_reader=neutral_reader)

    state_fearful = await updater_fearful.apply_event_shock(npc_id="npc-fearful", severity=60)
    state_neutral = await updater_neutral.apply_event_shock(npc_id="npc-neutral", severity=60)

    assert state_fearful.valence < state_neutral.valence, (
        f"Fearful NPC valence {state_fearful.valence} should be lower than "
        f"neutral NPC valence {state_neutral.valence}"
    )


@pytest.mark.asyncio
async def test_different_npcs_use_their_own_traits() -> None:
    """ISSUE-096: two NPCs sharing one updater receive trait-specific shock magnitudes."""
    store = EmotionStore()
    reader = _make_trait_reader({
        "npc-a": {TRAIT_FEAR_SENSITIVITY: 0.5},
        "npc-b": {TRAIT_FEAR_SENSITIVITY: 3.0},
    })
    updater = EmotionUpdater(emotion_store=store, trait_reader=reader)

    state_a = await updater.apply_event_shock(npc_id="npc-a", severity=60)
    state_b = await updater.apply_event_shock(npc_id="npc-b", severity=60)

    assert state_b.valence < state_a.valence, (
        f"High-fear NPC-B valence {state_b.valence} should be lower than "
        f"low-fear NPC-A valence {state_a.valence}"
    )


@pytest.mark.asyncio
async def test_emotion_updater_unchanged_without_trait_reader() -> None:
    """ISSUE-096: existing behaviour (no trait_reader) is unchanged — backward compat."""
    updater = await _make_updater()
    state = await updater.apply_event_shock(npc_id="npc-1", severity=60)
    # Vad default: valence_delta = min(30, 60//3)=20, new_valence=-20
    assert state.valence == -20
