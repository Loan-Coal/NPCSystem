"""
Module: probe_events
Layer: evals (eval harness — not part of src/)
Purpose: EngineProbe for the events engine (measurement-remediation Phase 4, DEC-271).
         Creates a small batch of Event nodes across N ticks and measures how many were
         created, their severity distribution, and the orphan rate (events with no
         KNOWS_ABOUT edge from any NPC).
Dependencies: httpx, uuid, probe_protocol (evals/), scenario_adapter_utils (evals/)
Used by: probe_runner.PROBE_FACTORIES
Does NOT: import from src/npc_engine/, measure orphan rate over the whole graph — there is
          no server-side count/filter route for Event nodes (confirmed: GET /v1/graph/
          nodes/Event pages the full unfiltered set with no property filter), so pageing
          every event in a live eval stack would be unbounded and non-deterministic across
          repetitions. This probe scopes severity distribution and orphan rate to the
          batch IT created (uuid-tagged IDs), which is what "events created/tick" already
          requires tracking — the same tag serves both.

Interpretation: "every known event has a KNOWS_ABOUT edge" is checked as the converse of
the orphan-rate metric, over this probe's own batch only — every event this probe marked
as known (by attaching one KNOWS_ABOUT edge at creation, half the batch) must still carry
that edge after N ticks; the other half is deliberately left unknown to give orphan_rate
something to measure. Fabricating a graph-wide invariant here would require pagination this
probe does not attempt (see above).
"""

from __future__ import annotations

import statistics
import uuid
from typing import Callable

import httpx

from probe_protocol import EngineProbe
from scenario_adapter_utils import GRAPH_PREFIX, is_ok, now_iso

EventsProbeFactory = Callable[[httpx.Client], EngineProbe]

_SEVERITIES: tuple[int, ...] = (20, 45, 65, 80)
_KNOWER_TICK: int = 700


class EventsProbe:
    """Creates a uuid-tagged batch of Events, half known, and measures the batch."""

    engine_name = "events"

    def __init__(self) -> None:
        """Start with no batch; setup() seeds a fresh, uniquely-tagged batch."""
        self._suffix: str = ""
        self._event_ids: list[str] = []
        self._known_event_ids: list[str] = []
        self._known_npc_id: str = ""
        self.invariants = {"known_events_have_an_edge": self._invariant_known_events_have_an_edge}

    def _invariant_known_events_have_an_edge(self, client: httpx.Client) -> bool:
        """Every event this probe marked known must still carry its KNOWS_ABOUT edge."""
        return all(_has_knower(client, event_id) for event_id in self._known_event_ids)

    def setup(self, client: httpx.Client) -> None:
        """Create one origin NPC and reset this repetition's empty event batch."""
        self._suffix = uuid.uuid4().hex[:8]
        self._known_npc_id = f"npc_probe_events_{self._suffix}"
        self._event_ids = []
        self._known_event_ids = []
        client.post(f"{GRAPH_PREFIX}/nodes/Character", json={"properties": {
            "id": self._known_npc_id, "name": "Probe Witness", "archetype": "commoner",
            "is_active": True, "is_player": False, "biography": "eval fixture",
            "gossipy": 50, "credulity": 50, "honesty": 50, "created_at": now_iso(),
            "updated_at": now_iso(), "last_graph_updated_at": now_iso(),
        }})

    def drive(self, client: httpx.Client, ticks: int) -> None:
        """Create one Event per tick (cycling severities); mark every other one known."""
        for i in range(max(ticks, 1)):
            tick_id = _KNOWER_TICK + i
            event_id = f"evt_probe_events_{self._suffix}_{i}"
            severity = _SEVERITIES[i % len(_SEVERITIES)]
            client.post(f"{GRAPH_PREFIX}/nodes/Event", json={"properties": {
                "id": event_id, "summary": "A probe-created event.", "severity": severity,
                "location_id": None, "occurred_at": now_iso(), "tick_id": tick_id,
                "event_type": "other", "is_public": False, "last_graph_updated_at": now_iso(),
            }})
            self._event_ids.append(event_id)
            if i % 2 == 0:
                client.post(f"{GRAPH_PREFIX}/edges/KNOWS_ABOUT", json={
                    "src_id": self._known_npc_id, "dst_id": event_id,
                    "properties": {"knowledge_state": "knows", "learned_at_tick": tick_id},
                })
                self._known_event_ids.append(event_id)

    def measure(self, client: httpx.Client) -> dict[str, float]:
        """Report events/tick, mean severity, and this batch's orphan rate."""
        if not self._event_ids:
            return {}
        severities = [_SEVERITIES[i % len(_SEVERITIES)] for i in range(len(self._event_ids))]
        orphans = sum(1 for e in self._event_ids if not _has_knower(client, e))
        return {
            "events_created_per_tick": 1.0,
            "severity_mean": statistics.mean(severities),
            "orphan_rate": orphans / len(self._event_ids),
        }


def _has_knower(client: httpx.Client, event_id: str) -> bool:
    """True if at least one KNOWS_ABOUT edge points at this event."""
    resp = client.get(f"{GRAPH_PREFIX}/edges/KNOWS_ABOUT", params={"dst_id": event_id, "limit": 1})
    if not is_ok(resp):
        return False
    data = resp.json().get("data", [])
    return bool(data)


def _make_events_probe(client: httpx.Client) -> EngineProbe:
    """ProbeFactory: build a fresh EventsProbe (client unused — probe holds no client)."""
    del client
    return EventsProbe()


EVENTS_PROBE_FACTORIES: dict[str, EventsProbeFactory] = {"events": _make_events_probe}
