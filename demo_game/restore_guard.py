"""
Module: restore_guard
Layer: demo_game (standalone CLI tool — no engine layer imports)
Purpose: Detect a live Neo4j writer before a destructive graph restore and refuse to proceed.
Dependencies: os, time, pydantic
Used by: demo_game.snapshot (do_restore)
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The probe samples the graph, waits, and samples again. The engine's tick
# autopilot writes :WorldState every `TICK_INTERVAL_SECONDS` (config.py:178,
# default 10s), so a window LONGER than that period is guaranteed to contain a
# tick boundary — a running autopilot is caught with certainty, not by luck.
# If TICK_INTERVAL_SECONDS is ever raised, raise this with it.
PROBE_SECONDS_DEFAULT = 12
PROBE_SECONDS_ENV = "SNAPSHOT_PROBE_SECONDS"

CYPHER_COUNT_NODES = "MATCH (n) RETURN count(n) AS node_count"
CYPHER_COUNT_RELS = "MATCH ()-[r]->() RETURN count(r) AS rel_count"
CYPHER_WORLD_STATE_CLOCKS = (
    "MATCH (w:WorldState)"
    " RETURN w.id AS id, w.tick_id AS tick_id,"
    " toString(w.last_updated_at) AS last_updated_at"
    " ORDER BY w.id"
)

REMEDY_HINT = "Stop the engine first:  docker compose stop app"


class LiveWriterDetectedError(RuntimeError):
    """Raised when the graph changes during the probe window.

    Attributes:
        changes: Human-readable ``field: before -> after`` lines describing what moved.
    """

    def __init__(self, changes: list[str]) -> None:
        self.changes = changes
        super().__init__("\n".join(changes))


class WorldClock(BaseModel):
    """The clock fields of one :WorldState node, as seen by the probe."""

    model_config = ConfigDict(frozen=True)

    id: str
    tick_id: int | None = None
    last_updated_at: str | None = None


class GraphFingerprint(BaseModel):
    """A cheap, comparable summary of graph state used to detect concurrent writes."""

    model_config = ConfigDict(frozen=True)

    node_count: int
    rel_count: int
    world_clocks: tuple[WorldClock, ...]


def graph_fingerprint(session: Any) -> GraphFingerprint:
    """Read a fingerprint of current graph state.

    Args:
        session: An open Neo4j sync session.
    Returns:
        Total node and relationship counts plus every :WorldState node's clock fields.
    """
    node_count = int(session.run(CYPHER_COUNT_NODES).single()["node_count"])
    rel_count = int(session.run(CYPHER_COUNT_RELS).single()["rel_count"])
    clocks = tuple(
        WorldClock(
            id=str(record["id"]),
            tick_id=record["tick_id"],
            last_updated_at=record["last_updated_at"],
        )
        for record in session.run(CYPHER_WORLD_STATE_CLOCKS)
    )
    return GraphFingerprint(node_count=node_count, rel_count=rel_count, world_clocks=clocks)


def probe_seconds() -> int:
    """Return the probe window length, from SNAPSHOT_PROBE_SECONDS or the default.

    Returns:
        Seconds to wait between the two samples. 0 disables the probe entirely.
    Raises:
        ValueError: If the environment variable is not a non-negative integer.
    """
    raw = os.environ.get(PROBE_SECONDS_ENV)
    if raw is None:
        return PROBE_SECONDS_DEFAULT
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{PROBE_SECONDS_ENV} must be an integer, got {raw!r}") from exc
    if value < 0:
        raise ValueError(f"{PROBE_SECONDS_ENV} must be >= 0, got {value}")
    return value


def assert_no_live_writer(
    session: Any,
    *,
    probe_seconds: int,
    sleep: Callable[[float], None] | None = None,
) -> None:
    """Refuse to continue if anything is writing to the graph.

    Samples the graph, waits *probe_seconds*, and samples again. A difference means
    another process (normally the engine's tick autopilot) holds the graph, and a
    destructive restore would race it.

    Args:
        session: An open Neo4j sync session.
        probe_seconds: Length of the probe window; 0 skips the probe.
        sleep: Injectable sleep, for tests. Defaults to time.sleep.
    Raises:
        LiveWriterDetectedError: If the graph changed across the window.
    """
    if probe_seconds <= 0:
        return
    wait = sleep if sleep is not None else time.sleep
    before = graph_fingerprint(session)
    wait(probe_seconds)
    after = graph_fingerprint(session)
    if before != after:
        raise LiveWriterDetectedError(describe_change(before, after))


def describe_change(before: GraphFingerprint, after: GraphFingerprint) -> list[str]:
    """Return ``field: before -> after`` lines for every field that moved.

    Args:
        before: Fingerprint taken at the start of the probe window.
        after: Fingerprint taken at the end of it.
    Returns:
        One line per differing field; empty if the fingerprints are equal.
    """
    changes: list[str] = []
    for field in ("node_count", "rel_count"):
        old, new = getattr(before, field), getattr(after, field)
        if old != new:
            changes.append(f"{field}: {old} -> {new}")
    changes.extend(_describe_clock_changes(before.world_clocks, after.world_clocks))
    return changes


def _describe_clock_changes(
    before: tuple[WorldClock, ...], after: tuple[WorldClock, ...]
) -> list[str]:
    """Return per-:WorldState difference lines between two clock tuples."""
    old_by_id = {clock.id: clock for clock in before}
    new_by_id = {clock.id: clock for clock in after}
    changes: list[str] = []
    for world_id in sorted(set(old_by_id) | set(new_by_id)):
        old, new = old_by_id.get(world_id), new_by_id.get(world_id)
        if old == new:
            continue
        if old is None or new is None:
            changes.append(f"WorldState {world_id!r}: {'appeared' if old is None else 'disappeared'}")
            continue
        for field in ("tick_id", "last_updated_at"):
            if getattr(old, field) != getattr(new, field):
                changes.append(
                    f"WorldState {world_id!r}.{field}: {getattr(old, field)} -> {getattr(new, field)}"
                )
    return changes
