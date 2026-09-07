"""
Module: probe_gossip
Layer: evals (eval harness — not part of src/)
Purpose: EngineProbe for the gossip engine (measurement-remediation Phase 4, DEC-271).
         Seeds one Event known by an origin NPC, drives N gossip ticks, and measures
         propagation reach, hop depth, and per-hop distortion delta — the last of which
         is ISSUE-228's own instrument: gossip distortion does not compound across hops,
         and this metric is how a fix (or a regression) would show up. It does not fix
         ISSUE-228; it measures it, per the plan's own "measure it" instruction.
Dependencies: httpx, uuid, probe_protocol (evals/), scenario_adapter_utils (evals/)
Used by: probe_runner.PROBE_FACTORIES
Does NOT: import from src/npc_engine/, hold state across repetitions (each setup() seeds
          a fresh, uniquely-suffixed Event and origin edge).

Interpretation choices (no hop_count / no path property exists on KNOWS_ABOUT — see
DEC-271): "no NPC knows an event it has no path to" is checked as "every non-origin
knower's KNOWS_ABOUT edge carries a source_character_id" — the only structural evidence
a KNOWS_ABOUT edge was reached by propagation rather than appearing without attribution.
"Hops-to-knowledge" and "distortion delta per hop" both read GET /v1/admin/gossip/trace/
{event_id}, the only route that reconstructs an ordered propagation chain, ordered by
learned_at_tick.
"""

from __future__ import annotations

import uuid
from typing import Callable

import httpx
from pydantic import BaseModel, ConfigDict

from probe_protocol import EngineProbe
from scenario_adapter_utils import ADMIN_PREFIX, GRAPH_PREFIX, is_ok, now_iso

GossipProbeFactory = Callable[[httpx.Client], EngineProbe]

_ORIGIN_TICK: int = 500
_SEVERITY: int = 65
_MAX_PAIRS: int = 20


class _GossipFixture(BaseModel):
    """One repetition's seeded Event and origin NPC, resolved once by setup()."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    location_id: str
    origin_npc_id: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _seed_event_and_origin(client: httpx.Client) -> _GossipFixture:
    """Create a fresh Event and mark one fresh Character as its origin knower."""
    suffix = uuid.uuid4().hex[:8]
    event_id, location_id, origin_id = f"evt_probe_gossip_{suffix}", f"loc_probe_gossip_{suffix}", f"npc_probe_gossip_{suffix}"
    client.post(f"{GRAPH_PREFIX}/nodes/Location", json={"properties": {
        "id": location_id, "name": "Probe Square", "description": "eval fixture",
        "last_graph_updated_at": now_iso(),
    }})
    client.post(f"{GRAPH_PREFIX}/nodes/Character", json={"properties": {
        "id": origin_id, "name": "Probe Origin", "archetype": "commoner", "is_active": True,
        "is_player": False, "biography": "eval fixture", "gossipy": 80, "credulity": 50,
        "honesty": 50, "created_at": now_iso(), "updated_at": now_iso(),
        "last_graph_updated_at": now_iso(),
    }})
    client.post(f"{GRAPH_PREFIX}/nodes/Event", json={"properties": {
        "id": event_id, "summary": "A stranger was seen bribing the tax collector.",
        "severity": _SEVERITY, "location_id": location_id, "occurred_at": now_iso(),
        "tick_id": _ORIGIN_TICK, "event_type": "crime", "is_public": False,
        "last_graph_updated_at": now_iso(),
    }})
    client.post(f"{GRAPH_PREFIX}/edges/KNOWS_ABOUT", json={
        "src_id": origin_id, "dst_id": event_id,
        "properties": {"knowledge_state": "knows", "learned_at_tick": _ORIGIN_TICK},
    })
    return _GossipFixture(event_id=event_id, location_id=location_id, origin_npc_id=origin_id)


def _run_gossip_ticks(client: httpx.Client, ticks: int) -> list[int]:
    """Run `ticks` gossip_tick batches starting after the origin tick, returning tick ids."""
    tick_ids = [_ORIGIN_TICK + i + 1 for i in range(max(ticks, 1))]
    for tick_id in tick_ids:
        client.post(f"{ADMIN_PREFIX}/batch/gossip_tick", json={"tick_override": tick_id, "max_pairs": _MAX_PAIRS})
    return tick_ids


def _fetch_knower_edges(client: httpx.Client, event_id: str) -> list[dict]:
    """List every KNOWS_ABOUT edge pointing at this event."""
    resp = client.get(f"{GRAPH_PREFIX}/edges/KNOWS_ABOUT", params={"dst_id": event_id, "limit": 200})
    if not is_ok(resp):
        return []
    data = resp.json().get("data", [])
    return data if isinstance(data, list) else []


def _fetch_trace_chain(client: httpx.Client, event_id: str) -> list[dict]:
    """Read the ordered propagation chain for one event, oldest knower first."""
    resp = client.get(f"{ADMIN_PREFIX}/gossip/trace/{event_id}")
    if not is_ok(resp):
        return []
    chain = resp.json().get("data", {}).get("chain", [])
    return chain if isinstance(chain, list) else []


def _distortion_deltas(chain: list[dict]) -> list[float]:
    """Consecutive distortion_level differences along the trace chain, hop 2 onward."""
    levels = [float(row.get("distortion_level") or 0) for row in chain if row.get("distortion_level") is not None]
    return [levels[i] - levels[i - 1] for i in range(1, len(levels))]


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------


class GossipProbe:
    """Seeds an Event known by one origin NPC, drives gossip ticks, measures propagation."""

    engine_name = "gossip"

    def __init__(self) -> None:
        """Start with no fixture; setup() seeds one fresh Event+origin per repetition."""
        self._fixture: _GossipFixture | None = None
        self.invariants = {"knowers_have_a_source": self._invariant_knowers_have_a_source}

    def _invariant_knowers_have_a_source(self, client: httpx.Client) -> bool:
        """Every KNOWS_ABOUT edge other than the origin's own carries a source_character_id."""
        if self._fixture is None:
            return True
        edges = _fetch_knower_edges(client, self._fixture.event_id)
        others = [e for e in edges if e.get("src_id") != self._fixture.origin_npc_id]
        return all(e.get("source_character_id") for e in others)

    def setup(self, client: httpx.Client) -> None:
        """Seed a fresh Event and origin-knower Character for this repetition."""
        self._fixture = _seed_event_and_origin(client)

    def drive(self, client: httpx.Client, ticks: int) -> None:
        """Run `ticks` gossip_tick batches over the seeded event."""
        _run_gossip_ticks(client, ticks)

    def measure(self, client: httpx.Client) -> dict[str, float]:
        """Report propagation reach, hop depth, and per-hop distortion delta."""
        if self._fixture is None:
            return {}
        event_id = self._fixture.event_id
        knowers = _fetch_knower_edges(client, event_id)
        chain = _fetch_trace_chain(client, event_id)
        deltas = _distortion_deltas(chain)
        metrics = {
            "propagation_reach": float(len(knowers)),
            "hops_to_knowledge": float(len(chain)),
        }
        if deltas:
            metrics["distortion_delta_per_hop_mean"] = sum(deltas) / len(deltas)
        return metrics


def _make_gossip_probe(client: httpx.Client) -> EngineProbe:
    """ProbeFactory: build a fresh GossipProbe (client unused — probe holds no client)."""
    del client
    return GossipProbe()


GOSSIP_PROBE_FACTORIES: dict[str, GossipProbeFactory] = {"gossip": _make_gossip_probe}
