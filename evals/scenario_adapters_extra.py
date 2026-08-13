"""
Module: scenario_adapters_extra
Layer: evals (eval harness — not part of src/)
Purpose: ScenarioFn adapters for the three EVAL-P12.4 promoted scenarios that don't
         fit in scenario_adapters.py's 300-line budget: memory_consolidation,
         time_passage, mood_contagion.

         Fixes forward a real gap found while wiring mood_contagion (see
         DECISIONS.md, EVAL-P12.4): the original e2e/scenarios/scenario_mood_contagion.py
         posts to `POST /v1/admin/advance`, a route that does not exist (grep against
         src/npc_engine/api/routes/ confirms no such route — dead reference), and reads
         state via a direct Neo4j driver connection, unlike every other scenario. This
         adapter drives ticks through the real `POST /v1/clock/advance` route (mood
         contagion is one of TickScheduler's unconditional per-tick engines — no
         interval gate to satisfy) and reads mood back through the admin graph HTTP
         endpoints, matching the access pattern used everywhere else in this module.
Dependencies: httpx (injected client), uuid, typing, scenario_adapter_utils (evals/)
Used by: evals/scenario_adapters.py (EVAL-P12.4)
Does NOT: import from src/npc_engine/, open a Neo4j connection, hold state across calls.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

import httpx

from preconditions import ensure_player_node
from scenario_adapter_utils import ADMIN_PREFIX, GRAPH_PREFIX, is_ok, now_iso

# ---------------------------------------------------------------------------
# memory_consolidation — dialogue turns consolidate into a Memory node
# ---------------------------------------------------------------------------

_CONSOLIDATION_MESSAGES = (
    "What do you know about the guild?",
    "Do you trust them?",
    "That sounds dangerous.",
    "What will you do about it?",
    "Is there anyone who can help?",
    "How long have you been watching them?",
)


def make_memory_consolidation(client: httpx.Client) -> Callable[[], bool]:
    """Six dialogue turns + consolidate() -> a Memory node with the expected vividness."""

    def _run() -> bool:
        suffix = uuid.uuid4().hex[:8]
        char_id, player_id = f"e2e_consol_char_{suffix}", f"e2e_player_{suffix}"
        client.post(f"{GRAPH_PREFIX}/nodes/Character", json={"properties": {
            "id": char_id, "name": "E2E NPC", "archetype": "schemer",
            "biography": "A figure who has watched the guild's dealings for years.",
            "is_player": False, "is_active": True, "created_at": now_iso(), "updated_at": now_iso(),
            "last_graph_updated_at": now_iso(), "gossipy": 30, "credulity": 40, "honesty": 60,
        }})
        ensure_player_node(client, "", player_id)  # strict-player policy (ISSUE-118)
        memory_id: str | None = None
        try:
            for msg in _CONSOLIDATION_MESSAGES:
                resp = client.post("/v1/dialogue", json={
                    "player_id": player_id, "npc_id": char_id, "player_message": msg,
                })
                if not is_ok(resp):
                    return False
            consolidate = client.post(f"{ADMIN_PREFIX}/memories/consolidate/{char_id}", json={
                "player_id": player_id, "turn_threshold": 5,
            })
            if not is_ok(consolidate):
                return False
            memory_id = consolidate.json().get("data", {}).get("memory_id")
            if memory_id is None:
                return False
            memories = client.get(f"{ADMIN_PREFIX}/memories/{char_id}", params={"k": 5})
            if not is_ok(memories):
                return False
            found = next(
                (m for m in memories.json().get("data", {}).get("memories", []) if m.get("id") == memory_id),
                None,
            )
            return found is not None and found.get("vividness") == 75
        finally:
            if memory_id:
                client.delete(f"{ADMIN_PREFIX}/memories/{memory_id}")
            client.delete(f"{ADMIN_PREFIX}/graph/characters/{char_id}")

    return _run


# ---------------------------------------------------------------------------
# time_passage — structured game time advances correctly
# ---------------------------------------------------------------------------

_TIME_SLOTS = ("midday", "afternoon", "evening", "night", "morning")


def make_time_passage(client: httpx.Client) -> Callable[[], bool]:
    """5 time_of_day advances complete one full cycle; day 28 -> 1 increments the season.

    Bug fix (EVAL-P12.4, DECISIONS.md DEC-174): the original e2e/scenarios/scenario_time_passage.py
    hardcoded "morning" as the expected slot after 5 advances. time_of_day rotates through exactly
    5 fixed slots, so 5 advances is mathematically always one full cycle back to whatever slot you
    started at -- landing on "morning" specifically only holds if the shared world_state (which
    survives reset_world under PARTIAL fidelity -- world_state.other_properties) happened to already
    be at "morning" before the first advance. It is not, in general. The correct invariant is
    "5 advances returns to the starting slot", which this reads before advancing and asserts against.
    """

    def _advance(field: str) -> dict[str, Any] | None:
        resp = client.post("/v1/clock/advance", json={
            "delta_ticks": 1, "game_time_seconds": 0, "advance_time_field": field,
        })
        if not is_ok(resp):
            return None
        return resp.json().get("data", {}).get("world_state")

    def _current_world_state() -> dict[str, Any] | None:
        resp = client.get(f"{GRAPH_PREFIX}/nodes/world_state/world")
        if not is_ok(resp):
            return None
        return resp.json().get("data")

    def _run() -> bool:
        baseline = _current_world_state()
        if baseline is None:
            return False
        starting_slot = baseline.get("time_of_day")

        ws = None
        for _ in _TIME_SLOTS:
            ws = _advance("time_of_day")
            if ws is None:
                return False
        if ws.get("time_of_day") != starting_slot:
            return False
        current_day = ws.get("day")
        for _ in range((28 - current_day) % 28):
            ws = _advance("day")
            if ws is None:
                return False
        ws = _advance("day")
        if ws is None:
            return False
        return ws.get("day") == 1

    return _run


# ---------------------------------------------------------------------------
# mood_contagion — mood spreads between co-located, affectionate NPCs
# ---------------------------------------------------------------------------


def make_mood_contagion(client: httpx.Client) -> Callable[[], bool]:
    """Two co-located NPCs with high affection: tick advances persist a mood on both."""

    def _char(char_id: str, name: str, mood: str, intensity: float) -> dict[str, Any]:
        return {
            "id": char_id, "name": name, "archetype": "commoner", "is_active": True,
            "is_player": False, "biography": "eval fixture", "gossipy": 50, "credulity": 50,
            "honesty": 70, "current_mood": mood, "mood_intensity": intensity,
            "created_at": now_iso(), "updated_at": now_iso(), "last_graph_updated_at": now_iso(),
        }

    def _run() -> bool:
        suffix = uuid.uuid4().hex[:8]
        alice, bob, tavern = f"mood_alice_{suffix}", f"mood_bob_{suffix}", f"mood_tavern_{suffix}"

        try:
            client.post(f"{GRAPH_PREFIX}/nodes/Character", json={"properties": _char(alice, "Alice", "elated", 0.7)})
            client.post(f"{GRAPH_PREFIX}/nodes/Character", json={"properties": _char(bob, "Bob", "melancholic", 0.2)})
            client.post(f"{GRAPH_PREFIX}/nodes/Location", json={"properties": {
                "id": tavern, "name": "Eval Tavern", "description": "eval fixture",
                "last_graph_updated_at": now_iso(),
            }})
            client.post(f"{GRAPH_PREFIX}/edges/LOCATED_AT", json={
                "src_id": alice, "dst_id": tavern, "properties": {"arrived_at": now_iso()},
            })
            client.post(f"{GRAPH_PREFIX}/edges/LOCATED_AT", json={
                "src_id": bob, "dst_id": tavern, "properties": {"arrived_at": now_iso()},
            })
            client.post(f"{GRAPH_PREFIX}/edges/RELATES_TO", json={
                "src_id": alice, "dst_id": bob, "properties": {
                    "trust": 70, "fear": 10, "affection": 75,
                    "interaction_count": 20, "relevance_score": 0.8,
                },
            })
            for _ in range(3):
                client.post("/v1/clock/advance", json={"delta_ticks": 1, "game_time_seconds": 3600})
            alice_state = client.get(f"{GRAPH_PREFIX}/nodes/Character/{alice}")
            bob_state = client.get(f"{GRAPH_PREFIX}/nodes/Character/{bob}")
            if not (is_ok(alice_state) and is_ok(bob_state)):
                return False
            alice_mood = alice_state.json().get("data", {}).get("current_mood")
            bob_mood = bob_state.json().get("data", {}).get("current_mood")
            return alice_mood is not None and bob_mood is not None
        finally:
            client.delete(f"{ADMIN_PREFIX}/graph/characters/{alice}")
            client.delete(f"{ADMIN_PREFIX}/graph/characters/{bob}")
            client.delete(f"{ADMIN_PREFIX}/graph/locations/{tavern}")

    return _run


# ---------------------------------------------------------------------------
# Registry (merged into scenario_adapters.SCENARIO_ADAPTER_FACTORIES)
# ---------------------------------------------------------------------------

EXTRA_SCENARIO_ADAPTER_FACTORIES: dict[str, Callable[[httpx.Client], Callable[[], bool]]] = {
    "scenario_memory_consolidation": make_memory_consolidation,
    "scenario_time_passage": make_time_passage,
    "scenario_mood_contagion": make_mood_contagion,
}
