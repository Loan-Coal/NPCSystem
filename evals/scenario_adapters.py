"""
Module: scenario_adapters
Layer: evals (eval harness — not part of src/)
Purpose: ScenarioFn adapters for the six EVAL-P12.4 promoted scenarios, wrapping
         each e2e/scenarios/scenario_*.py's intent as a bare `() -> bool` callable
         sequence_runner.run_sequence can call k times. This module holds the three
         pure-HTTP scenarios (gossip_chain, grief_persistence, reputation_drift) and
         the registry; memory_consolidation, time_passage and mood_contagion live in
         scenario_adapters_extra.py to keep both files under the 300-line limit.

         Fixes forward two real gaps found while wiring this (see DECISIONS.md,
         EVAL-P12.4): gossip_chain and grief_persistence hardcoded scenario-vocabulary
         IDs (npc_1, npc_6, elder_1, loc_market) with no pass/fail predicate — both are
         wired through evals/world_map.py here, with an explicit success predicate
         authored for each. Every adapter uses a fresh, unique entity id per
         repetition (uuid suffix) so k repeated calls never collide on a create
         endpoint that is not an upsert.
Dependencies: httpx (injected client), uuid, world_map (evals/), scenario_adapter_utils
Used by: evals/sequence_rates.py (EVAL-P12.4)
Does NOT: import from src/npc_engine/, hold any state across calls.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

import httpx

from preconditions import ensure_player_node
from scenario_adapter_utils import ADMIN_PREFIX, GRAPH_PREFIX, is_ok, now_iso
from scenario_adapters_extra import EXTRA_SCENARIO_ADAPTER_FACTORIES
from world_map import WORLD_MAP

# ---------------------------------------------------------------------------
# gossip_chain — event awareness propagates across a RELATES_TO edge
# ---------------------------------------------------------------------------


def make_gossip_chain(client: httpx.Client) -> Callable[[], bool]:
    """Event created at a location + a gossip tick -> the related NPC learns of it."""
    known_npc = WORLD_MAP.resolve("scenario_gossip_chain", "npc_1")
    distant_npc = WORLD_MAP.resolve("scenario_gossip_chain", "npc_6")
    location = WORLD_MAP.resolve("scenario_gossip_chain", "loc_market")

    def _run() -> bool:
        event_id = f"evt_gossip_chain_{uuid.uuid4().hex[:8]}"
        client.post(f"{GRAPH_PREFIX}/nodes/Event", json={"properties": {
            "id": event_id, "summary": "A cloaked figure exchanges a package at the market.",
            "severity": 65, "location_id": location, "occurred_at": now_iso(),
            "tick_id": 500, "event_type": "crime", "is_public": False,
            "last_graph_updated_at": now_iso(),
        }})
        client.post(f"{GRAPH_PREFIX}/edges/KNOWS_ABOUT", json={
            "src_id": known_npc, "dst_id": event_id,
            "properties": {"knowledge_state": "knows", "learned_at_tick": 500},
        })
        for tick in (501, 502):
            client.post(f"{ADMIN_PREFIX}/batch/gossip_tick", json={"tick_override": tick, "max_pairs": 20})
        state = client.get(f"/v1/npc/{distant_npc}/state")
        if not is_ok(state):
            return False
        # /v1/npc/{id}/state returns NPCStateResponse directly (no OkEnvelope "data" wrapper).
        events = state.json().get("events", [])
        return any(e.get("event", {}).get("id") == event_id for e in events)

    return _run


# ---------------------------------------------------------------------------
# grief_persistence — emotion carries across dialogue turns
# ---------------------------------------------------------------------------


def make_grief_persistence(client: httpx.Client) -> Callable[[], bool]:
    """Grief delivered in turn 1 measurably persists into the NPC's emotion after turn 2."""
    npc = WORLD_MAP.resolve("scenario_grief_persistence", "elder_1")
    location = WORLD_MAP.resolve("scenario_grief_persistence", "loc_market")

    def _run() -> bool:
        session_id = f"scenario_grief_persistence:{uuid.uuid4().hex[:8]}"
        player = f"player_grief_{uuid.uuid4().hex[:8]}"
        ensure_player_node(client, "", player)  # strict-player policy (ISSUE-118)
        turn1 = client.post("/v1/dialogue", json={
            "player_id": player, "npc_id": npc, "location_id": location,
            "session_id": session_id,
            "player_message": "Elder, my daughter passed away last night. She was only seven.",
        })
        turn2 = client.post("/v1/dialogue", json={
            "player_id": player, "npc_id": npc, "location_id": location,
            "session_id": session_id,
            "player_message": "I came back to talk. I still feel so lost.",
        })
        if not (is_ok(turn1) and is_ok(turn2)):
            return False
        emotion = client.get(f"/v1/npc/{npc}/emotion")
        if not is_ok(emotion):
            return False
        # /v1/npc/{id}/emotion returns EmotionResponse directly (no OkEnvelope "data" wrapper).
        return float(emotion.json().get("valence", 0.0)) < 0.0

    return _run


# ---------------------------------------------------------------------------
# reputation_drift — reputation arithmetic and clamping
# ---------------------------------------------------------------------------


def make_reputation_drift(client: httpx.Client) -> Callable[[], bool]:
    """+60 then -90 reputation clamps to -30."""

    def _char_props(char_id: str, name: str, is_player: bool) -> dict[str, Any]:
        return {
            "id": char_id, "name": name, "archetype": "commoner", "biography": "eval fixture",
            "is_player": is_player, "is_active": True, "created_at": now_iso(), "updated_at": now_iso(),
            "last_graph_updated_at": now_iso(), "gossipy": 50, "credulity": 50, "honesty": 50,
        }

    def _run() -> bool:
        suffix = uuid.uuid4().hex[:8]
        faction_id, npc_id, player_id = f"rep_faction_{suffix}", f"rep_npc_{suffix}", f"rep_player_{suffix}"

        client.post(f"{ADMIN_PREFIX}/factions/", json={
            "id": faction_id, "name": "Eval Faction", "archetype": "political", "is_active": True,
        })
        client.post(f"{GRAPH_PREFIX}/nodes/Character", json={"properties": _char_props(npc_id, "NPC", False)})
        client.post(f"{ADMIN_PREFIX}/factions/{faction_id}/members", json={
            "character_id": npc_id, "role": "member", "status": "active",
        })
        client.post(f"{GRAPH_PREFIX}/nodes/Character", json={"properties": _char_props(player_id, "Player", True)})
        client.put(f"{ADMIN_PREFIX}/characters/{player_id}/reputation/{faction_id}", json={"standing": 60})
        client.post(f"{ADMIN_PREFIX}/characters/{player_id}/reputation/{faction_id}/adjust", json={"delta": -90})
        final = client.get(f"{GRAPH_PREFIX}/characters/{player_id}/reputation/{faction_id}")
        if not is_ok(final):
            return False
        return bool(final.json().get("data", {}).get("standing") == -30)

    return _run


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SCENARIO_ADAPTER_FACTORIES: dict[str, Callable[[httpx.Client], Callable[[], bool]]] = {
    "scenario_gossip_chain": make_gossip_chain,
    "scenario_grief_persistence": make_grief_persistence,
    "scenario_reputation_drift": make_reputation_drift,
    **EXTRA_SCENARIO_ADAPTER_FACTORIES,
}
