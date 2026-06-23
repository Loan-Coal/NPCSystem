"""
test_player_model_engine.py - Unit tests for PlayerModelEngine.

Does NOT: perform I/O, touch Neo4j, or call LLMs.

Dependencies injected: None (pure engine, all inputs passed directly).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_player_model_update_from_scalars() -> None:
    """Engine derives perceived_trust from relation scalars (trust + affection - fear)."""
    from npc_engine.engines.player_model.player_model_engine import (
        PlayerModelEngine,
        PlayerModelInput,
    )

    engine = PlayerModelEngine()
    result = engine.derive(
        PlayerModelInput(
            npc_id="npc_a",
            player_id="player_1",
            trust=70,
            fear=10,
            affection=20,
            interaction_signal=None,
        )
    )

    # composite = clamp(70 + 20 - 10, 0, 100) = clamp(80, 0, 100) = 80
    assert result.perceived_trust == 80
    assert result.npc_id == "npc_a"
    assert result.player_id == "player_1"


def test_player_model_trust_clamped_to_zero() -> None:
    """perceived_trust is clamped to 0 when composite score is negative."""
    from npc_engine.engines.player_model.player_model_engine import (
        PlayerModelEngine,
        PlayerModelInput,
    )

    engine = PlayerModelEngine()
    result = engine.derive(
        PlayerModelInput(
            npc_id="npc_b",
            player_id="player_1",
            trust=0,
            fear=100,
            affection=0,
            interaction_signal=None,
        )
    )

    assert result.perceived_trust == 0


def test_player_model_trust_clamped_to_100() -> None:
    """perceived_trust is clamped to 100 when composite exceeds maximum."""
    from npc_engine.engines.player_model.player_model_engine import (
        PlayerModelEngine,
        PlayerModelInput,
    )

    engine = PlayerModelEngine()
    result = engine.derive(
        PlayerModelInput(
            npc_id="npc_c",
            player_id="player_1",
            trust=200,
            fear=0,
            affection=200,
            interaction_signal=None,
        )
    )

    assert result.perceived_trust == 100


def test_player_model_intent_hostile_low_trust() -> None:
    """perceived_intent is 'hostile' when trust is below HOSTILE_TRUST_THRESHOLD."""
    from npc_engine.engines.player_model.player_model_engine import (
        PlayerModelEngine,
        PlayerModelInput,
        INTENT_HOSTILE,
    )

    engine = PlayerModelEngine()
    result = engine.derive(
        PlayerModelInput(
            npc_id="npc_d",
            player_id="player_1",
            trust=0,
            fear=80,
            affection=0,
            interaction_signal=None,
        )
    )

    assert result.perceived_intent == INTENT_HOSTILE


def test_player_model_intent_friendly_high_trust() -> None:
    """perceived_intent is 'friendly' when trust is above FRIENDLY_TRUST_THRESHOLD."""
    from npc_engine.engines.player_model.player_model_engine import (
        PlayerModelEngine,
        PlayerModelInput,
        INTENT_FRIENDLY,
    )

    engine = PlayerModelEngine()
    result = engine.derive(
        PlayerModelInput(
            npc_id="npc_e",
            player_id="player_1",
            trust=90,
            fear=0,
            affection=80,
            interaction_signal=None,
        )
    )

    assert result.perceived_intent == INTENT_FRIENDLY


def test_player_model_update_output_is_pydantic() -> None:
    """derive() returns a Pydantic BaseModel (PlayerModelUpdate)."""
    from pydantic import BaseModel

    from npc_engine.engines.player_model.player_model_engine import (
        PlayerModelEngine,
        PlayerModelInput,
        PlayerModelUpdate,
    )

    engine = PlayerModelEngine()
    result = engine.derive(
        PlayerModelInput(
            npc_id="npc_f",
            player_id="player_1",
            trust=50,
            fear=20,
            affection=10,
            interaction_signal=None,
        )
    )

    assert isinstance(result, PlayerModelUpdate)
    assert isinstance(result, BaseModel)
