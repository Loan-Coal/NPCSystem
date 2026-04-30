"""
delta_log_manager.py - Pure utilities for relation delta log append and window math.

Does NOT: persist logs or mutate graph edges in storage.

Dependencies injected: None.
"""

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
    """Return a new bounded delta log with one appended entry."""

    new_entry = RelationDeltaEntry(
        tick_id=tick_id,
        cause_id=cause_id,
        deltas=dict(deltas),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    combined_log = [*delta_log, new_entry]
    return combined_log[-max_entries:]


def compute_window_sum(delta_log: list[RelationDeltaEntry], field: str, window_size: int) -> int:
    """Compute sum of a relation field over the last N entries."""

    window_entries = delta_log[-window_size:]
    return sum(entry.deltas.get(field, 0) for entry in window_entries)
