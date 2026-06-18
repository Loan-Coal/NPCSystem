"""
delta_log_manager.py - Pure utilities for relation delta log append and window math.
Layer: services
Purpose: (auto-detected — review)

Does NOT: persist logs or mutate graph edges in storage.

Dependencies injected: None.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict


class RelationDeltaEntry(BaseModel):
    """Single relation delta log entry."""

    tick_id: int
    cause_id: str
    deltas: dict[str, int]
    timestamp: str

    model_config = ConfigDict(frozen=True)


def append_delta(
    delta_log: list[RelationDeltaEntry],
    tick_id: int,
    cause_id: str,
    deltas: dict[str, int],
    max_entries: int,
) -> list[RelationDeltaEntry]:
    """Return a new bounded delta log with one appended entry.

    Args:
        delta_log: Existing immutable log of prior relation delta entries.
        tick_id: Game tick identifier for the new entry.
        cause_id: Identifier of the event or action that caused the delta.
        deltas: Field-name-to-delta-value mapping for the new entry.
        max_entries: Maximum number of entries to retain (oldest are dropped).

    Returns:
        New list containing all prior entries plus the new entry, trimmed to max_entries.
    """

    new_entry = RelationDeltaEntry(
        tick_id=tick_id,
        cause_id=cause_id,
        deltas=dict(deltas),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    combined_log = [*delta_log, new_entry]
    return combined_log[-max_entries:]


def compute_window_sum(delta_log: list[RelationDeltaEntry], field: str, window_size: int) -> int:
    """Compute sum of a relation field over the last N entries.

    Args:
        delta_log: Log of prior relation delta entries to scan.
        field: Relation field name (e.g. "trust", "fear") to sum.
        window_size: Number of most-recent entries to include in the sum.

    Returns:
        Integer sum of the field's delta values across the window, defaulting to 0 for absent entries.
    """

    window_entries = delta_log[-window_size:]
    return sum(entry.deltas.get(field, 0) for entry in window_entries)
