"""
modifier_bounds_validator.py - Validates and clamps relation deltas with window caps.

Does NOT: write relation changes to the graph.

Dependencies injected: None.
"""

from dataclasses import dataclass

from graph.edge_schemas import RelationDeltaEntry
from mutation.delta_log_manager import compute_window_sum


MIN_RELATION_VALUE = 0
MAX_RELATION_VALUE = 100
RELATION_FIELDS = ("trust", "fear", "affection")


@dataclass(frozen=True)
class DeltaValidationConfig:
    """Configuration for relation delta constraints."""

    max_delta_per_turn: int
    max_delta_per_window: int
    relation_window_size: int


@dataclass(frozen=True)
class RelationDeltaExceededError(Exception):
    """Raised when requested delta exceeds configured per-turn/window bounds."""

    field: str
    requested_delta: int
    max_allowed: int
    context: str

    def __str__(self) -> str:
        """Return full violation context for logs and API mapping."""

        return (
            "RelationDeltaExceededError("
            f"field={self.field}, "
            f"requested_delta={self.requested_delta}, "
            f"max_allowed={self.max_allowed}, "
            f"context={self.context}"
            ")"
        )


def validate_deltas(
    proposed_deltas: dict[str, int],
    delta_log: list[RelationDeltaEntry],
    config: DeltaValidationConfig,
) -> dict[str, int]:
    """Validate per-turn and window bounds and return normalized deltas."""

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
    """Return clamped relation values in [0, 100]."""

    clamped: dict[str, int] = {}
    for field in RELATION_FIELDS:
        next_value = current_values.get(field, 50) + deltas.get(field, 0)
        clamped[field] = max(MIN_RELATION_VALUE, min(MAX_RELATION_VALUE, next_value))
    return clamped
