"""
test_modifier_bounds_validator_coverage.py - Unit tests for mutation.modifier_bounds_validator.

Does NOT: execute graph I/O.

Dependencies injected: None.
"""

from __future__ import annotations

import pytest

from npc_engine.mutation.modifier_bounds_validator import (
    DeltaValidationConfig,
    clamp_relation_values,
    validate_deltas,
)
from npc_engine.utils.errors import RelationDeltaExceededError

_CONFIG = DeltaValidationConfig(
    max_delta_per_turn=15,
    max_delta_per_window=40,
    relation_window_size=10,
)


# ---------------------------------------------------------------------------
# validate_deltas — happy paths
# ---------------------------------------------------------------------------

def test_validate_deltas_within_bounds_returns_normalized() -> None:
    """Deltas within per-turn limit must be returned as-is."""
    result = validate_deltas({"trust": 5, "fear": -3, "affection": 0}, [], _CONFIG)
    assert result["trust"] == 5
    assert result["fear"] == -3
    assert result["affection"] == 0


def test_validate_deltas_zero_delta_is_accepted() -> None:
    """Zero deltas for all fields must pass validation without error."""
    result = validate_deltas({}, [], _CONFIG)
    assert all(v == 0 for v in result.values())


def test_validate_deltas_at_max_turn_boundary() -> None:
    """Delta exactly at max_delta_per_turn must not raise."""
    result = validate_deltas({"trust": 15}, [], _CONFIG)
    assert result["trust"] == 15


def test_validate_deltas_at_negative_max_turn_boundary() -> None:
    """Delta exactly at -max_delta_per_turn must not raise."""
    result = validate_deltas({"fear": -15}, [], _CONFIG)
    assert result["fear"] == -15


# ---------------------------------------------------------------------------
# validate_deltas — error paths
# ---------------------------------------------------------------------------

def test_validate_deltas_exceeds_per_turn_raises() -> None:
    """Delta one unit over max_delta_per_turn must raise RelationDeltaExceededError."""
    with pytest.raises(RelationDeltaExceededError) as exc_info:
        validate_deltas({"trust": 16}, [], _CONFIG)
    assert exc_info.value.field == "trust"
    assert exc_info.value.context == "per_turn"


def test_validate_deltas_negative_exceeds_per_turn_raises() -> None:
    """Negative delta one unit under -max_delta_per_turn must raise."""
    with pytest.raises(RelationDeltaExceededError) as exc_info:
        validate_deltas({"fear": -16}, [], _CONFIG)
    assert exc_info.value.field == "fear"
    assert exc_info.value.context == "per_turn"


def test_validate_deltas_exceeds_window_raises() -> None:
    """If window sum + proposed delta exceed max_delta_per_window, must raise."""
    from npc_engine.mutation.delta_log_manager import RelationDeltaEntry
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat()
    # Build a log that already has 35 points of trust accumulated
    existing_log = [
        RelationDeltaEntry(tick_id=i, cause_id="ev", deltas={"trust": 5}, timestamp=ts)
        for i in range(7)  # 7 * 5 = 35
    ]
    # Proposing +10 → window sum = 35 + 10 = 45 > 40
    with pytest.raises(RelationDeltaExceededError) as exc_info:
        validate_deltas({"trust": 10}, existing_log, _CONFIG)
    assert exc_info.value.context == "window"


# ---------------------------------------------------------------------------
# clamp_relation_values
# ---------------------------------------------------------------------------

def test_clamp_keeps_value_within_bounds() -> None:
    """Values within [0, 100] must be returned unchanged."""
    result = clamp_relation_values({"trust": 50, "fear": 30, "affection": 70}, {"trust": 5, "fear": -5, "affection": 0})
    assert result["trust"] == 55
    assert result["fear"] == 25
    assert result["affection"] == 70


def test_clamp_caps_at_maximum() -> None:
    """Clamped value must not exceed 100."""
    result = clamp_relation_values({"trust": 95, "fear": 0, "affection": 0}, {"trust": 15, "fear": 0, "affection": 0})
    assert result["trust"] == 100


def test_clamp_floors_at_minimum() -> None:
    """Clamped value must not go below 0."""
    result = clamp_relation_values({"trust": 5, "fear": 0, "affection": 0}, {"trust": -10, "fear": 0, "affection": 0})
    assert result["trust"] == 0


def test_clamp_at_exact_boundaries() -> None:
    """Values at exactly 0 and 100 must be returned without change."""
    result = clamp_relation_values({"trust": 0, "fear": 100, "affection": 50}, {"trust": 0, "fear": 0, "affection": 0})
    assert result["trust"] == 0
    assert result["fear"] == 100
