"""
modifier_bounds_validator.py - Validates and clamps relation deltas with window caps.
Layer: services
Purpose: Validates and clamps relation deltas with window caps.

Does NOT: write relation changes to the graph.

Dependencies injected: None.
"""
from __future__ import annotations

from dataclasses import dataclass

from npc_engine.mutation.delta_log_manager import RelationDeltaEntry, compute_window_sum
from npc_engine.utils.errors import RelationDeltaExceededError


MIN_RELATION_VALUE = 0
MAX_RELATION_VALUE = 100
RELATION_FIELDS = ("trust", "fear", "affection")


@dataclass(frozen=True)
class DeltaValidationConfig:
    """Configuration for relation delta constraints."""

    max_delta_per_turn: int
    max_delta_per_window: int
    relation_window_size: int


def validate_deltas(
    proposed_deltas: dict[str, int],
    delta_log: list[RelationDeltaEntry],
    config: DeltaValidationConfig,
) -> dict[str, int]:
    """Validate per-turn and window bounds and return normalized deltas.

    Args:
        proposed_deltas: Mapping of relation field names to proposed integer deltas.
        delta_log: Historical delta log used to compute rolling window sums.
        config: Constraint configuration specifying max per-turn and window limits.

    Returns:
        Dict of validated and normalized delta values for all RELATION_FIELDS.

    Raises:
        RelationDeltaExceededError: If any field exceeds the per-turn or window cap.
    """

    validated: dict[str, int] = {}
    for field in RELATION_FIELDS:
        delta = proposed_deltas.get(field, 0)
        if abs(delta) > config.max_delta_per_turn:
            raise RelationDeltaExceededError(
                field=field,
                requested_delta=delta,
                max_allowed=config.max_delta_per_turn,
                context="per_turn",
            )
        window_sum = compute_window_sum(delta_log=delta_log, field=field, window_size=config.relation_window_size)
        if abs(window_sum + delta) > config.max_delta_per_window:
            raise RelationDeltaExceededError(
                field=field,
                requested_delta=delta,
                max_allowed=config.max_delta_per_window,
                context="window",
            )
        validated[field] = int(delta)
    return validated


def clamp_relation_values(current_values: dict[str, int], deltas: dict[str, int]) -> dict[str, int]:
    """Return clamped relation values in [0, 100].

    Args:
        current_values: Current relation field values before applying deltas.
        deltas: Validated delta values to apply to each relation field.

    Returns:
        New dict with each relation field clamped to [MIN_RELATION_VALUE, MAX_RELATION_VALUE].
    """

    clamped: dict[str, int] = {}
    for field in RELATION_FIELDS:
        next_value = current_values.get(field, 50) + deltas.get(field, 0)
        clamped[field] = max(MIN_RELATION_VALUE, min(MAX_RELATION_VALUE, next_value))
    return clamped
